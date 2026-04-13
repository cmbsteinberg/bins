#!/usr/bin/env python3
"""
Orchestrator for the full scraper sync pipeline.

Flow:
  1. Fetch input.json from UKBCD (source of truth for needed councils)
  2. Wipe all scrapers so stale files never linger across syncs
  3. Run HACS sync (clone, patch, copy scrapers)
  4. Filter HACS scrapers: remove any whose gov.uk prefix isn't in input.json
  5. Run UKBCD sync (fills gaps + builds lad_lookup.json with scraper IDs)
  6. Regenerate test cases (HACS + UKBCD)
  7. Regenerate postcode lookup (postcode -> LAD code parquet)

Usage:
    uv run python -m pipeline.sync_all
    uv run python -m pipeline.sync_all --include-unmerged
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys

import httpx

from pipeline.shared import (
    PIPELINE_DIR,
    PROJECT_ROOT,
    SCRAPERS_DIR,
    extract_gov_uk_prefix,
    extract_url_from_scraper,
    load_overrides,
    normalise_council_name,
    normalise_domain,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

INPUT_JSON_URL = "https://raw.githubusercontent.com/robbrad/UKBinCollectionData/master/uk_bin_collection/tests/input.json"
NEEDED_COUNCILS_PATH = PIPELINE_DIR / ".needed_councils.json"


def fetch_input_json() -> dict:
    """Fetch input.json from UKBCD GitHub."""
    logger.info("Fetching input.json from UKBCD...")
    resp = httpx.get(INPUT_JSON_URL, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    data = resp.json()
    logger.info("Fetched %d council entries from input.json", len(data))
    return data


def build_needed_identifiers(input_data: dict) -> set[str]:
    """Build a broad set of identifiers for councils listed in input.json.

    Extracts three kinds of identifier per entry so that HACS scrapers can be
    matched even when the input.json URL isn't a *.gov.uk domain:
      1. gov.uk prefix from the URL  (e.g. "sutton")
      2. normalised council name from the key  (e.g. "bristol" from BristolCityCouncil)
      3. primary domain word from non-gov URLs (e.g. "basildon" from mybasildon.powerappsportals.com)
    """
    ids: set[str] = set()
    for key, val in input_data.items():
        if not isinstance(val, dict):
            continue

        # 1. Normalised key (most reliable — always present)
        norm = normalise_council_name(key)
        if norm:
            ids.add(norm)

        url = val.get("url", "")
        if not url:
            continue

        # 2. gov.uk prefix from URL
        prefix = extract_gov_uk_prefix(url)
        if prefix:
            ids.add(prefix)

        # 3. Domain-based heuristic for non-gov URLs (PowerApps, fixmystreet, etc.)
        domain = normalise_domain(url)
        # e.g. "mybasildon.powerappsportals.com" → try "basildon"
        #      "bristolcouncil.powerappsportals.com" → try "bristol"
        first_label = domain.split(".")[0]
        # Strip common prefixes like "my", "online", "waste-services"
        for strip_prefix in ("my", "online", "apps", "forms", "waste", "maps"):
            if first_label.startswith(strip_prefix) and len(first_label) > len(strip_prefix):
                candidate = first_label[len(strip_prefix):].lstrip("-")
                if len(candidate) >= 4:  # avoid spurious short matches
                    ids.add(normalise_council_name(candidate))

    logger.info(
        "Built %d council identifiers from %d input.json entries",
        len(ids),
        sum(1 for v in input_data.values() if isinstance(v, dict)),
    )
    return ids


def filter_hacs_scrapers(needed_ids: set[str]) -> list[str]:
    """Remove HACS scrapers whose council isn't needed by input.json.

    Uses multiple matching strategies:
      1. gov.uk prefix from scraper URL
      2. normalised scraper filename
      3. normalised scraper TITLE

    Returns list of removed scraper names.
    """
    import ast

    overrides = load_overrides()
    override_hacs = {
        entry["hacs_scraper"] for entry in overrides.get("hacs_to_ukbcd", {}).values()
    }

    removed = []
    for path in sorted(SCRAPERS_DIR.glob("hacs_*.py")):
        if path.stem in override_hacs:
            continue

        # Strategy 1: gov.uk prefix from scraper URL
        url = extract_url_from_scraper(path)
        url_prefix = extract_gov_uk_prefix(url) if url else None

        # Strategy 2: normalised filename (strip hacs_ prefix + domain suffix)
        fname_norm = normalise_council_name(path.stem.removeprefix("hacs_"))

        # Strategy 3: TITLE from scraper source
        title_norm = None
        try:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == "TITLE"
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                ):
                    title_norm = normalise_council_name(node.value.value)
                    break
        except SyntaxError:
            pass

        candidates = [c for c in (url_prefix, fname_norm, title_norm) if c]
        matched = any(c in needed_ids for c in candidates)

        if not matched:
            path.unlink()
            removed.append(path.stem)
            logger.info(
                "Removed unneeded HACS scraper: %s (no match in input.json; "
                "url_prefix=%s, fname=%s, title=%s)",
                path.stem,
                url_prefix,
                fname_norm,
                title_norm,
            )

    return removed


def run_shell(cmd: list[str], description: str) -> None:
    """Run a shell command, streaming output."""
    logger.info("Running: %s", description)
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        logger.error("%s failed with exit code %d", description, result.returncode)
        sys.exit(result.returncode)


def save_needed_councils(needed_ids: set[str]) -> None:
    """Save needed council identifiers to a temp file for other scripts to reference."""
    NEEDED_COUNCILS_PATH.write_text(json.dumps(sorted(needed_ids), indent=2))


def main():
    args = sys.argv[1:]
    include_unmerged = "--include-unmerged" in args

    # 1. Fetch input.json and build needed set
    input_data = fetch_input_json()
    needed_ids = build_needed_identifiers(input_data)
    save_needed_councils(needed_ids)

    # 2. Wipe all scrapers so stale files never linger across syncs
    print("\n" + "=" * 50)
    print("=== Cleaning scrapers directory ===")
    print("=" * 50)
    removed_count = 0
    for path in SCRAPERS_DIR.glob("*.py"):
        if path.name == "__init__.py":
            continue
        path.unlink()
        removed_count += 1
    logger.info("Removed %d scraper files.", removed_count)

    # 3. Run HACS sync (clone, patch, copy)
    # Clear version file so HACS sync always runs after a full wipe
    hacs_version_file = PIPELINE_DIR / "hacs" / ".upstream_version"
    hacs_version_file.unlink(missing_ok=True)

    print("\n" + "=" * 50)
    print("=== Syncing HACS scrapers ===")
    print("=" * 50)
    run_shell(
        ["bash", str(PIPELINE_DIR / "hacs" / "sync.sh")],
        "HACS sync",
    )

    # 4. Filter HACS scrapers against input.json
    print("\n" + "=" * 50)
    print("=== Filtering HACS scrapers against input.json ===")
    print("=" * 50)
    removed = filter_hacs_scrapers(needed_ids)
    if removed:
        logger.info(
            "Removed %d stale HACS scrapers: %s", len(removed), ", ".join(removed)
        )
    else:
        logger.info("No stale HACS scrapers found.")

    # 5. Run UKBCD sync (fills gaps + builds lad_lookup.json)
    print("\n" + "=" * 50)
    print("=== Syncing UKBCD scrapers (filling gaps) ===")
    print("=" * 50)
    ukbcd_cmd = ["bash", str(PIPELINE_DIR / "ukbcd" / "sync.sh")]
    if include_unmerged:
        ukbcd_cmd.append("--include-unmerged")
    run_shell(ukbcd_cmd, "UKBCD sync")

    # 6. Regenerate test cases (after filtering, so stale scrapers are excluded)
    print("\n" + "=" * 50)
    print("=== Regenerating test cases ===")
    print("=" * 50)
    run_shell(
        ["uv", "run", "python", "-m", "pipeline.hacs.generate_test_lookup"],
        "HACS test cases",
    )
    run_shell(
        ["uv", "run", "python", "-m", "pipeline.ukbcd.generate_test_lookup"],
        "UKBCD test cases",
    )

    # 7. Regenerate postcode lookup (postcode -> LAD code parquet)
    print("\n" + "=" * 50)
    print("=== Regenerating postcode lookup ===")
    print("=" * 50)
    run_shell(
        ["uv", "run", "python", "-m", "scripts.lookup.create_lookup_table"],
        "postcode lookup regeneration",
    )

    # Cleanup temp file
    NEEDED_COUNCILS_PATH.unlink(missing_ok=True)

    print("\n" + "=" * 50)
    print("Done. Run 'uv run pytest tests/test_ci.py -v' to verify.")
    print("=" * 50)


if __name__ == "__main__":
    main()
