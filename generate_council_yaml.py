#!/usr/bin/env python3
"""Generate YAML summaries for each council file showing request patterns and parsing methods."""

import re
import yaml
from pathlib import Path
from collections import defaultdict


def extract_request_details(content):
    """Extract request details from requests.get/post/etc calls."""
    requests_list = []

    # Find requests.get/post/put/delete calls (multi-line aware)
    pattern = (
        r"(?:requests|session)\.(get|post|put|delete|patch)\s*\(\s*([^,]+?)(?:,|$)"
    )
    matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)

    for match in matches:
        method = match.group(1).upper()
        url_part = match.group(2).strip()

        # Clean up the URL part
        if url_part.startswith(('f"', "f'")):
            url = url_part
        else:
            url = url_part.strip("\"'")

        request_obj = {
            "method": method,
            "url": url if url else None,
        }
        requests_list.append(request_obj)

    return requests_list


def extract_variable_definition(content, var_name):
    """Extract the definition of a variable."""
    # Pattern: var_name = {...}
    pattern = rf'{var_name}\s*=\s*(\{{[^}}]*\}}|["\'][^"\']*["\']|\w+)'
    match = re.search(pattern, content)
    if match:
        return match.group(1)
    return None


def extract_urls(content):
    """Extract URLs from requests and selenium calls."""
    urls = []

    # Find requests.get/post calls with URLs
    patterns = [
        r'(?:requests|session)\.\w+\s*\(\s*f?["\']([^"\']+)["\']',
        r'driver\.get\s*\(\s*f?["\']([^"\']+)["\']',
        r'url\s*=\s*f?["\']([^"\']+)["\']',
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            url = match.group(1)
            # Skip incomplete URLs like "https://" or "http://"
            if url in ("http://", "https://"):
                continue
            if url and not url.startswith("http"):
                # Handle f-strings
                if "{" in url:
                    urls.append(f'f"{url}"')
                else:
                    urls.append(url)
            elif url and url.startswith(("http://", "https://")):
                urls.append(url)

    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    return unique_urls


def extract_request_body(content):
    """Extract data, json, params from requests - looking for actual values."""
    body_params = {}

    # Find inline dictionaries assigned to data/json/params
    patterns = {
        "data": [
            r"data\s*=\s*(\{[^}]*\})",
            r"data=(\{[^}]*\})",
        ],
        "json": [
            r"json\s*=\s*(\{[^}]*\})",
            r"json=(\{[^}]*\})",
        ],
        "params": [
            r"params\s*=\s*(\{[^}]*\})",
            r"params=(\{[^}]*\})",
        ],
        "form_data": [
            r"form_data\s*=\s*(\{[^}]*\})",
        ],
    }

    for key, patterns_list in patterns.items():
        for pattern in patterns_list:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                value = match.group(1)
                # Truncate if too long
                if len(value) > 150:
                    value = value[:150] + "..."
                body_params[key] = value
                break

    return body_params


def extract_uprn_postcode_usage(content):
    """Extract lines containing uprn or postcode, excluding check_uprn/check_postcode and .get calls."""
    usages = []

    # Split into lines
    lines = content.split("\n")

    for line in lines:
        # Check if line contains uprn or postcode (case insensitive)
        if not re.search(r"\b(?:uprn|postcode)\b", line, re.IGNORECASE):
            continue

        # Skip lines that are just function calls to check_uprn or check_postcode
        if re.search(r"check_(?:uprn|postcode)\s*\(", line):
            continue

        # Skip lines that are just .get() calls
        if re.search(r"\.get\s*\(\s*['\"](?:uprn|postcode)['\"]", line):
            continue

        # Clean up and add
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            usages.append(stripped)

    # Remove duplicates while preserving order
    seen = set()
    unique_usages = []
    for usage in usages:
        if usage not in seen:
            seen.add(usage)
            unique_usages.append(usage)

    return unique_usages


def analyze_council_file(filepath):
    """Analyze a single council file."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Detect request types
    has_requests = bool(re.search(r"\brequests\b", content))
    has_selenium = bool(
        re.search(r"\bfrom\s+selenium\b|\bimport\s+selenium\b", content)
    )

    if has_requests and has_selenium:
        request_type = "both"
    elif has_requests:
        request_type = "requests"
    elif has_selenium:
        request_type = "selenium"
    else:
        request_type = "none"

    # Detect parsing methods
    parsing_methods = []
    if re.search(r"\bfrom\s+bs4\b|\bimport\s+bs4\b", content):
        parsing_methods.append("bs4")
    if re.search(r"\bimport\s+json\b|\bfrom\s+json\b", content):
        parsing_methods.append("json")
    if re.search(r"\bre\.(findall|search|match|sub)\b", content):
        parsing_methods.append("regex")
    if re.search(r"xml\.etree|ElementTree", content):
        parsing_methods.append("xml")
    if re.search(r"\bpandas\b|\bpd\b", content):
        parsing_methods.append("pandas")

    # Extract request details
    urls = extract_urls(content)
    body_params = extract_request_body(content)
    uprn_postcode_usages = extract_uprn_postcode_usage(content)

    # Detect specific HTTP methods
    http_methods = set()
    if has_requests:
        if re.search(r"requests\.get\b", content):
            http_methods.add("GET")
        if re.search(r"requests\.post\b", content):
            http_methods.add("POST")
        if re.search(r"requests\.put\b", content):
            http_methods.add("PUT")

    return {
        "filename": filepath.name,
        "request_type": request_type,
        "http_methods": list(http_methods) if http_methods else None,
        "parsing_methods": parsing_methods if parsing_methods else None,
        "urls": urls if urls else None,
        "body_params": body_params if body_params else None,
        "uprn_postcode_usages": uprn_postcode_usages if uprn_postcode_usages else None,
    }


def main():
    councils_dir = Path(
        "/Users/christophersteinberg/Documents/GitHub/bins/UKBinCollectionData/uk_bin_collection/uk_bin_collection/councils"
    )
    output_dir = Path(
        "/Users/christophersteinberg/Documents/GitHub/bins/council_summaries"
    )
    output_dir.mkdir(exist_ok=True)

    # Analyze all files
    py_files = sorted(councils_dir.glob("*.py"))

    print(f"Analyzing {len(py_files)} council files...")

    for filepath in py_files:
        analysis = analyze_council_file(filepath)

        # Create YAML structure
        yaml_data = {
            "metadata": {
                "file": analysis["filename"],
                "request_type": analysis["request_type"],
            }
        }

        if analysis["http_methods"]:
            yaml_data["metadata"]["http_methods"] = analysis["http_methods"]

        if analysis["parsing_methods"]:
            yaml_data["parsing"] = {"methods": analysis["parsing_methods"]}

        if analysis["urls"] or analysis["body_params"]:
            yaml_data["request"] = {}
            if analysis["urls"]:
                yaml_data["request"]["urls"] = analysis["urls"]
            if analysis["body_params"]:
                yaml_data["request"]["body"] = analysis["body_params"]

        if analysis["uprn_postcode_usages"]:
            yaml_data["data_inputs"] = {
                "uprn_postcode_usages": analysis["uprn_postcode_usages"]
            }

        # Write YAML file
        output_file = output_dir / f"{filepath.stem}.yaml"
        with open(output_file, "w") as f:
            yaml.dump(
                yaml_data,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    print(f"Generated YAML files in {output_dir}")

    # Print summary stats
    stats = defaultdict(int)
    for filepath in py_files:
        analysis = analyze_council_file(filepath)
        stats[analysis["request_type"]] += 1

    print("\nRequest Type Summary:")
    for req_type, count in sorted(stats.items()):
        print(f"  {req_type:12} : {count:3} files")


if __name__ == "__main__":
    main()
