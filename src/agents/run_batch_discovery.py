#!/usr/bin/env python3
"""
Batch discovery runner for all councils.

Loads councils from postcodes_by_council.csv and runs discovery for each.
"""

import polars as pl
from pathlib import Path
from run_discovery import discover_council
import time

def run_batch_discovery(limit: int = None):
    """
    Run discovery for all councils in the CSV.

    Args:
        limit: Optional limit on number of councils to process (for testing)
    """
    # Load council data
    csv_path = Path(__file__).parent.parent.parent / "data" / "postcodes_by_council.csv"
    df = pl.read_csv(csv_path)

    if limit:
        df = df.head(limit)

    print(f"\n{'='*60}")
    print(f"Batch Discovery - Processing {len(df)} councils")
    print(f"{'='*60}\n")

    results = []

    for row in df.iter_rows(named=True):
        council_name = row['Authority Name']
        url = row['URL']
        postcode = row['postcode']

        print(f"\n[{len(results) + 1}/{len(df)}] Processing: {council_name}")

        try:
            result = discover_council(council_name, url, postcode)
            results.append({
                'council': council_name,
                'status': 'success',
                'result': result
            })
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                'council': council_name,
                'status': 'failed',
                'error': str(e)
            })

        # Rate limiting - don't hammer councils
        time.sleep(2)

    # Summary
    print(f"\n{'='*60}")
    print("Batch Discovery Complete!")
    print(f"{'='*60}\n")

    successes = sum(1 for r in results if r['status'] == 'success')
    failures = len(results) - successes

    print(f"Successful: {successes}/{len(results)}")
    print(f"Failed: {failures}/{len(results)}")

    if failures > 0:
        print("\nFailed councils:")
        for r in results:
            if r['status'] == 'failed':
                print(f"  - {r['council']}: {r['error']}")

    return results


if __name__ == "__main__":
    import sys

    # For testing, default to first 5 councils
    limit = 5 if len(sys.argv) < 2 else None

    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            limit = None
        else:
            limit = int(sys.argv[1])

    print(f"Running batch discovery (limit: {limit or 'all'})")
    results = run_batch_discovery(limit=limit)
