"""
Integration tests for council bin lookups

Tests the bin_lookup runtime against actual council APIs using test
parameters from input.json
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

# Add parent directory to path to import bin_lookup
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bin_lookup import lookup_bin_times_async, list_available_councils


# ============================================================================
# TEST PARAMETER LOADING
# ============================================================================


def load_test_parameters() -> Dict[str, Dict[str, Any]]:
    """Load test parameters from input.json"""
    input_file = Path("extraction/data/input.json")

    if not input_file.exists():
        raise FileNotFoundError(f"Cannot find {input_file}")

    with open(input_file, "r") as f:
        all_params = json.load(f)

    # Filter out metadata fields
    metadata_fields = [
        "LAD24CD",
        "wiki_name",
        "wiki_note",
        "wiki_command_url_override",
        "url",  # URL is often not needed for direct API calls
    ]

    test_params = {}
    for council_name, params in all_params.items():
        # Remove metadata
        filtered = {k: v for k, v in params.items() if k not in metadata_fields}
        if filtered:  # Only include if there are test parameters
            test_params[council_name] = filtered

    return test_params


# ============================================================================
# TEST EXECUTION
# ============================================================================


async def _test_single_council(
    council_name: str, test_params: Dict[str, Any], timeout: int = 30
) -> Dict[str, Any]:
    """Test a single council lookup"""
    try:
        response = await lookup_bin_times_async(
            council_name, test_params, timeout=timeout
        )

        return {
            "council": council_name,
            "status": "success",
            "http_status": response.status_code,
            "response_length": len(response.text),
            "content_type": response.headers.get("content-type", "unknown"),
        }

    except NotImplementedError as e:
        return {
            "council": council_name,
            "status": "not_implemented",
            "error": str(e),
        }

    except ValueError as e:
        return {
            "council": council_name,
            "status": "config_error",
            "error": str(e),
        }

    except Exception as e:
        return {
            "council": council_name,
            "status": "failed",
            "error": str(e),
            "error_type": type(e).__name__,
        }


async def run_integration_tests(
    max_tests: int = None,
    only_councils: List[str] = None,
    skip_selenium: bool = True,
    concurrency: int = 10,
) -> Dict[str, Any]:
    """
    Run integration tests for council lookups

    Args:
        max_tests: Maximum number of councils to test (None for all)
        only_councils: Only test these specific councils (None for all)
        skip_selenium: Skip councils marked as selenium
        concurrency: Number of concurrent requests (default: 10)

    Returns:
        Dictionary with test results and statistics
    """
    print("=" * 80)
    print("Council Bin Lookup Integration Tests")
    print("=" * 80)

    # Load test parameters
    print("\nLoading test parameters from input.json...")
    test_params = load_test_parameters()
    print(f"Loaded test parameters for {len(test_params)} councils")

    # Get available councils
    available_councils = set(list_available_councils())
    print(f"Found {len(available_councils)} council configs")

    # Filter councils to test
    if only_councils:
        councils_to_test = [c for c in only_councils if c in available_councils]
    else:
        # Test councils that have both config and test params
        councils_to_test = sorted(available_councils & set(test_params.keys()))

    if max_tests:
        councils_to_test = councils_to_test[:max_tests]

    print(
        f"\nTesting {len(councils_to_test)} councils with concurrency={concurrency}\n"
    )

    # Track progress
    completed = 0
    total = len(councils_to_test)
    start_time = time.time()

    # Semaphore to limit concurrency
    semaphore = asyncio.Semaphore(concurrency)

    async def test_with_semaphore(
        council_name: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        nonlocal completed
        async with semaphore:
            result = await _test_single_council(council_name, params)
            completed += 1

            # Print status
            status_msg = f"[{completed}/{total}] {council_name}..."
            if result["status"] == "success":
                status_code = result.get("http_status")
                if status_code == 200:
                    print(f"{status_msg} ✅ {status_code}")
                else:
                    print(f"{status_msg} ⚠️  {status_code}")
            elif result["status"] == "not_implemented":
                if not skip_selenium:
                    print(f"{status_msg} ⏸️  (selenium)")
            elif result["status"] == "config_error":
                print(f"{status_msg} ⚙️  {result['error'][:50]}")
            else:
                print(f"{status_msg} ❌ {result.get('error_type', 'Error')}")

            return result

    # Create all tasks
    tasks = [
        test_with_semaphore(council_name, test_params.get(council_name, {}))
        for council_name in councils_to_test
    ]

    # Run all tests concurrently
    results = await asyncio.gather(*tasks)

    elapsed = time.time() - start_time

    # Calculate statistics
    stats = {
        "total": len(results),
        "success": sum(1 for r in results if r["status"] == "success"),
        "http_200": sum(1 for r in results if r.get("http_status") == 200),
        "http_other": sum(
            1
            for r in results
            if r["status"] == "success" and r.get("http_status") != 200
        ),
        "not_implemented": sum(1 for r in results if r["status"] == "not_implemented"),
        "config_error": sum(1 for r in results if r["status"] == "config_error"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "elapsed_seconds": round(elapsed, 2),
    }

    # Print summary
    print(f"\n{'=' * 80}")
    print("Test Summary")
    print(f"{'=' * 80}")
    print(
        f"Total tested: {stats['total']} in {stats['elapsed_seconds']}s ({stats['total'] / elapsed:.1f} councils/sec)"
    )
    print(
        f"  ✅ HTTP 200: {stats['http_200']} ({stats['http_200'] / stats['total'] * 100:.1f}%)"
    )
    print(f"  ⚠️  HTTP other: {stats['http_other']}")
    print(f"  ⏸️  Not implemented (selenium): {stats['not_implemented']}")
    print(f"  ⚙️  Config errors: {stats['config_error']}")
    print(f"  ❌ Failed: {stats['failed']}")
    print(f"{'=' * 80}")

    return {
        "results": results,
        "stats": stats,
    }


# ============================================================================
# MAIN
# ============================================================================


def main():
    """Run integration tests from command line"""
    import argparse

    parser = argparse.ArgumentParser(description="Test council bin lookups")
    parser.add_argument(
        "--max",
        type=int,
        help="Maximum number of councils to test",
    )
    parser.add_argument(
        "--council",
        action="append",
        help="Test specific council (can be repeated)",
    )
    parser.add_argument(
        "--include-selenium",
        action="store_true",
        help="Include selenium councils in output",
    )
    parser.add_argument(
        "--save-results",
        type=str,
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=50,
        help="Number of concurrent requests (default: 50)",
    )

    args = parser.parse_args()

    # Run tests (always async)
    test_data = asyncio.run(
        run_integration_tests(
            max_tests=args.max,
            only_councils=args.council,
            skip_selenium=not args.include_selenium,
            concurrency=args.concurrency,
        )
    )

    # Save results if requested
    if args.save_results:
        with open(args.save_results, "w") as f:
            json.dump(test_data, f, indent=2)
        print(f"\nResults saved to: {args.save_results}")


if __name__ == "__main__":
    main()
