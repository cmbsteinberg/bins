"""Pytest plugin to write structured test results to tests/test_output.json."""

import json
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "test_output.json"


_results: list[dict] = []


def pytest_runtest_logreport(report):
    if report.when != "call":
        return

    # Extract council name from the test id (e.g. "test_lookup[allerdale_gov_uk_Keswick]")
    node_id = report.nodeid
    council = ""
    label = ""
    if "[" in node_id:
        param_str = node_id.split("[", 1)[1].rstrip("]")
        # The id format is "{council}_{label}" — council ends at a _gov_uk boundary
        for suffix in ("_gov_uk", "_gov_uk"):
            idx = param_str.find(suffix)
            if idx != -1:
                council = param_str[: idx + len(suffix)]
                label = param_str[idx + len(suffix) + 1 :]
                break

    entry = {
        "council": council,
        "label": label,
        "status": report.outcome,  # "passed", "failed", "skipped"
        "duration": round(report.duration, 2),
    }

    if report.failed:
        msg = str(report.longrepr)
        # Extract the short assertion message
        for line in msg.splitlines():
            if "AssertionError" in line or "assert " in line:
                entry["error_summary"] = line.strip()
                break
        # Try to extract the API error detail
        if "— {" in msg:
            try:
                json_str = msg.split("— ", 1)[1].split("\n")[0]
                detail = json.loads(json_str)
                entry["error_detail"] = detail.get("detail", json_str)
            except (json.JSONDecodeError, IndexError):
                pass
        if "error_detail" not in entry:
            # Fallback: grab the response body from the assertion
            for line in msg.splitlines():
                if '"detail"' in line:
                    try:
                        start = line.index("{")
                        detail = json.loads(line[start:])
                        entry["error_detail"] = detail.get("detail", "")
                    except (ValueError, json.JSONDecodeError):
                        pass
                    break
        if "error_detail" not in entry and "error_summary" not in entry:
            # Last resort: first meaningful line of the repr
            entry["error_summary"] = msg.splitlines()[-1].strip()[:200]

    _results.append(entry)


def pytest_sessionfinish(session, exitstatus):
    results = _results
    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "results": results,
    }

    # Group failures by error_detail for easy scanning
    failure_categories: dict[str, list[str]] = {}
    for r in results:
        if r["status"] == "failed":
            key = r.get("error_detail", r.get("error_summary", "unknown"))
            failure_categories.setdefault(key, []).append(r["council"])
    summary["failure_categories"] = {
        k: {"count": len(v), "councils": v}
        for k, v in sorted(failure_categories.items(), key=lambda x: -len(x[1]))
    }

    OUTPUT_PATH.write_text(json.dumps(summary, indent=2) + "\n")
