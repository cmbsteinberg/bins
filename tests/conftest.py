"""Pytest plugin to write structured test results to tests/test_output.json."""

import json
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "test_output.json"

_results: list[dict] = []


def pytest_runtest_logreport(report):
    if report.when != "call":
        return

    node_id = report.nodeid

    # Extract council and label from parametrized id
    # e.g. "test_scraper_lookup[allerdale_gov_uk_Test_001]"
    council = ""
    label = ""
    if "[" in node_id:
        param_str = node_id.split("[", 1)[1].rstrip("]")
        # The id format is "{council}_{label}" — council ends at a _gov_uk boundary
        for suffix in ("_gov_uk",):
            idx = param_str.find(suffix)
            if idx != -1:
                council = param_str[: idx + len(suffix)]
                label = param_str[idx + len(suffix) + 1 :]
                break

    entry = {
        "node_id": node_id,
        "council": council,
        "label": label,
        "status": report.outcome,  # "passed", "failed", "skipped"
        "duration": round(report.duration, 2),
    }

    if report.failed:
        msg = str(report.longrepr)
        entry["full_message"] = msg

        # Extract structured fields from the failure message
        for line in msg.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("UPRN/address_id:"):
                entry["uprn"] = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("Query params:"):
                # Query params span multiple lines as JSON; grab inline value
                entry["query_params_raw"] = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("Status code:"):
                entry["status_code"] = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("Error detail:"):
                entry["error_detail"] = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("Exception:"):
                entry["exception"] = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("Response keys:"):
                entry["response_keys"] = line_stripped.split(":", 1)[1].strip()

        # Categorisation key for grouping
        if "error_detail" in entry:
            entry["failure_category"] = entry["error_detail"]
        elif "exception" in entry:
            entry["failure_category"] = entry["exception"]
        elif "status_code" in entry:
            entry["failure_category"] = f"HTTP {entry['status_code']}"
        else:
            # Fallback: last non-empty line
            entry["failure_category"] = msg.splitlines()[-1].strip()[:200]

        # Also extract error_summary: the first line starting with "Expected" or "Response" or "Request"
        for line in msg.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith(("Expected ", "Response ", "Request ")):
                entry["error_summary"] = line_stripped[:200]
                break

    _results.append(entry)


def pytest_sessionfinish(session, exitstatus):
    results = _results
    passed = [r for r in results if r["status"] == "passed"]
    failed = [r for r in results if r["status"] == "failed"]
    skipped = [r for r in results if r["status"] == "skipped"]

    summary = {
        "total": len(results),
        "passed": len(passed),
        "failed": len(failed),
        "skipped": len(skipped),
    }

    # Group failures by category for easy scanning
    failure_categories: dict[str, list[dict]] = {}
    for r in failed:
        key = r.get("failure_category", "unknown")
        failure_categories.setdefault(key, []).append({
            "council": r["council"],
            "label": r["label"],
            "uprn": r.get("uprn", ""),
            "status_code": r.get("status_code", ""),
            "error_summary": r.get("error_summary", ""),
            "duration": r["duration"],
        })

    summary["failure_categories"] = {
        k: {"count": len(v), "councils": v}
        for k, v in sorted(failure_categories.items(), key=lambda x: -len(x[1]))
    }

    # Per-council results for quick lookup
    summary["results"] = results

    OUTPUT_PATH.write_text(json.dumps(summary, indent=2) + "\n")
