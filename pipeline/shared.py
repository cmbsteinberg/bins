"""Shared utilities for the hacs and ukbcd pipeline scripts."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from urllib.parse import urlparse

# Paths
PIPELINE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PIPELINE_DIR.parent
API_DIR = PROJECT_ROOT / "api"
SCRAPERS_DIR = API_DIR / "scrapers"
LAD_LOOKUP_PATH = API_DIR / "data" / "lad_lookup.json"
OVERRIDES_PATH = PIPELINE_DIR / "overrides.json"

# Overly broad domains that should never be used as lookup keys
BLOCKED_DOMAINS = {
    "gov.uk",
    "calendar.google.com",
    "www.gov.uk",
}


def normalise_domain(url: str) -> str:
    """Extract bare domain from a URL."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    domain = urlparse(url).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def extract_gov_uk_prefix(url: str) -> str | None:
    """Extract the prefix before .gov.uk (or .gov.wales) from a URL.

    E.g. "https://online.aberdeenshire.gov.uk" -> "aberdeenshire"
         "https://www.allerdale.gov.uk" -> "allerdale"
         "https://anglesey.gov.wales" -> "anglesey"
         "https://apps.cloud9technologies.com" -> None (not gov.uk)
    """
    domain = normalise_domain(url)
    parts = domain.split(".")
    try:
        gov_idx = parts.index("gov")
    except ValueError:
        return None
    if gov_idx == 0:
        return None
    return parts[gov_idx - 1]


def extract_url_from_scraper(path: Path) -> str | None:
    """Parse the URL = '...' constant from a scraper file using AST."""
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "URL"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    return None


def build_hacs_domain_lookup(scrapers_dir: Path) -> dict[str, str]:
    """Build domain -> scraper name mapping from hacs scraper files on disk."""
    lookup: dict[str, str] = {}
    for path in sorted(scrapers_dir.glob("hacs_*.py")):
        url = extract_url_from_scraper(path)
        if not url:
            continue
        domain = normalise_domain(url)
        lookup[domain] = path.stem
    return lookup


def load_overrides() -> dict:
    """Load the pipeline overrides config."""
    if not OVERRIDES_PATH.exists():
        return {}
    return json.loads(OVERRIDES_PATH.read_text())
