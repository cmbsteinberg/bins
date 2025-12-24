#!/usr/bin/env python3
"""Analyze council .py scripts and categorize by imports."""

import os
import re
from pathlib import Path
from collections import defaultdict

def analyze_file(filepath):
    """Analyze a Python file for import statements and UPRN usage patterns."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    has_selenium = bool(re.search(r'\bfrom\s+selenium\b|\bimport\s+selenium\b', content))
    has_requests = bool(re.search(r'\brequests\b', content))
    has_bs4 = bool(re.search(r'\bfrom\s+bs4\b|\bimport\s+bs4\b|\bBeautifulSoup\b', content))
    has_json = bool(re.search(r'\bfrom\s+json\b|\bimport\s+json\b', content))

    # Check for f-strings containing {uprn} or {user_uprn}
    has_uprn_fstring = bool(re.search(r'f["\'].*\{(?:user_)?uprn\}.*["\']', content))

    # Check for any mention of uprn (case-insensitive)
    has_any_uprn = bool(re.search(r'\b(?:user_)?uprn\b', content, re.IGNORECASE))

    # Categorize UPRN usage
    if has_uprn_fstring:
        uprn_usage = 'uprn_fstring'
    elif has_any_uprn:
        uprn_usage = 'uprn_mention'
    else:
        uprn_usage = 'none'

    return {
        'selenium': has_selenium,
        'requests': has_requests,
        'bs4': has_bs4,
        'json': has_json,
        'uprn_usage': uprn_usage,
    }

def main():
    councils_dir = Path('/Users/christophersteinberg/Documents/GitHub/bins/UKBinCollectionData/uk_bin_collection/uk_bin_collection/councils')

    # Categories for HTTP library
    http_categories = defaultdict(list)
    # Categories for BS4
    bs4_categories = defaultdict(list)
    # Categories for JSON
    json_categories = defaultdict(list)
    # Categories for UPRN usage method
    uprn_usage_categories = defaultdict(list)

    # Analyze all Python files
    py_files = list(councils_dir.glob('*.py'))

    for filepath in py_files:
        imports = analyze_file(filepath)
        filename = filepath.name

        # Categorize by HTTP library
        if imports['selenium'] and imports['requests']:
            http_cat = 'both'
        elif imports['selenium']:
            http_cat = 'selenium'
        elif imports['requests']:
            http_cat = 'requests'
        else:
            http_cat = 'none'

        http_categories[http_cat].append(filename)

        # Categorize by BS4
        bs4_cat = 'bs4' if imports['bs4'] else 'no_bs4'
        bs4_categories[bs4_cat].append(filename)

        # Categorize by JSON
        json_cat = 'json' if imports['json'] else 'no_json'
        json_categories[json_cat].append(filename)

        # Categorize by UPRN usage method
        uprn_usage_categories[imports['uprn_usage']].append(filename)

    # Print summary statistics
    print("=" * 70)
    print("COUNCIL IMPORT ANALYSIS")
    print("=" * 70)
    print(f"\nTotal files analyzed: {len(py_files)}\n")

    print("HTTP LIBRARY USAGE")
    print("-" * 70)
    for category in ['selenium', 'requests', 'both', 'none']:
        count = len(http_categories[category])
        percentage = (count / len(py_files) * 100) if py_files else 0
        print(f"  {category:12} : {count:3} files ({percentage:5.1f}%)")

    print("\nBEAUTIFULSOUP4 USAGE")
    print("-" * 70)
    for category in ['bs4', 'no_bs4']:
        count = len(bs4_categories[category])
        percentage = (count / len(py_files) * 100) if py_files else 0
        label = 'uses bs4' if category == 'bs4' else 'no bs4'
        print(f"  {label:12} : {count:3} files ({percentage:5.1f}%)")

    print("\nJSON IMPORT USAGE")
    print("-" * 70)
    for category in ['json', 'no_json']:
        count = len(json_categories[category])
        percentage = (count / len(py_files) * 100) if py_files else 0
        label = 'imports json' if category == 'json' else 'no json'
        print(f"  {label:12} : {count:3} files ({percentage:5.1f}%)")

    print("\nUPRN USAGE METHOD")
    print("-" * 70)
    for category in ['uprn_fstring', 'uprn_mention', 'none']:
        count = len(uprn_usage_categories[category])
        percentage = (count / len(py_files) * 100) if py_files else 0
        if category == 'uprn_fstring':
            label = 'f-string'
        elif category == 'uprn_mention':
            label = 'any mention'
        else:
            label = 'no mention'
        print(f"  {label:16} : {count:3} files ({percentage:5.1f}%)")

    print("\nCROSS-TABULATION: HTTP LIBRARY × BS4 USAGE")
    print("-" * 70)

    # Create cross-tabulation
    cross_tab = defaultdict(lambda: defaultdict(int))
    for filepath in py_files:
        imports = analyze_file(filepath)
        if imports['selenium'] and imports['requests']:
            http_cat = 'both'
        elif imports['selenium']:
            http_cat = 'selenium'
        elif imports['requests']:
            http_cat = 'requests'
        else:
            http_cat = 'none'

        bs4_cat = 'bs4' if imports['bs4'] else 'no_bs4'
        cross_tab[http_cat][bs4_cat] += 1

    # Print cross-tabulation table
    print(f"{'':12} | {'bs4':>8} | {'no_bs4':>8} | {'Total':>8}")
    print("-" * 50)
    for http_cat in ['selenium', 'requests', 'both', 'none']:
        bs4_count = cross_tab[http_cat]['bs4']
        no_bs4_count = cross_tab[http_cat]['no_bs4']
        total = bs4_count + no_bs4_count
        print(f"{http_cat:12} | {bs4_count:>8} | {no_bs4_count:>8} | {total:>8}")

    print("=" * 70)

if __name__ == '__main__':
    main()
