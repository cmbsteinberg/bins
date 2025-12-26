import json
import time
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os

load_dotenv()


# ============================================================================
# STRUCTURED OUTPUT SCHEMA FOR GEMINI ANALYSIS
# ============================================================================


class NetworkAnalysisResult(BaseModel):
    """Analysis of network requests to propose a requests-based alternative"""

    council_name: str
    original_playwright_required: bool  # Was Playwright actually needed?

    # If we can replace with requests:
    alternative_request_type: Optional[
        Literal[
            "single_api",
            "token_then_api",
            "id_lookup_then_api",
            "still_needs_selenium",
        ]
    ] = None
    api_urls: Optional[List[str]] = None
    api_methods: Optional[List[str]] = None
    api_headers: Optional[Dict[str, str]] = None  # Any special headers needed
    api_payload_example: Optional[str] = None  # Example POST body if needed

    # Analysis
    key_requests: Optional[List[str]] = None  # URLs of important requests
    notes: Optional[str] = None
    confidence: Optional[Literal["high", "medium", "low"]] = None


# ============================================================================
# NETWORK CAPTURE & PLAYWRIGHT EXECUTION
# ============================================================================


def should_capture_request(resource_type: str, url: str) -> bool:
    """Filter network requests to only capture relevant ones"""
    # Include these resource types
    if resource_type in ["xhr", "fetch", "document"]:
        # Exclude common noise
        noise_patterns = [
            "google-analytics",
            "googletagmanager",
            "doubleclick",
            "facebook.com/tr",
            "analytics",
            "pixel",
            "/ads/",
            "fonts.googleapis",
            "fonts.gstatic",
            ".woff",
            ".ttf",
            ".ico",
        ]

        url_lower = url.lower()
        return not any(pattern in url_lower for pattern in noise_patterns)

    return False


def execute_playwright_and_capture(
    council_name: str, playwright_code: str, input_params: Dict[str, Any]
) -> Optional[List[Dict[str, Any]]]:
    """
    Execute playwright code (synchronously) and capture network requests
    Returns list of captured requests or None if failed
    """
    captured_requests = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()

            # Set up network listener at context level (captures all pages)
            def handle_request(request):
                try:
                    resource_type = request.resource_type
                    url = request.url

                    if should_capture_request(resource_type, url):
                        request_data = {
                            "url": url,
                            "method": request.method,
                            "resourceType": resource_type,
                            "headers": request.headers,
                            "postData": request.post_data,
                        }

                        # Try to get response details when available
                        try:
                            response = request.response()
                            if response:
                                request_data["responseStatus"] = response.status
                                request_data["responseHeaders"] = response.headers
                        except Exception:
                            pass

                        captured_requests.append(request_data)
                except Exception as e:
                    print(f"  ⚠️  Error capturing request: {str(e)}")

            # Attach listener to context, not page
            context.on("request", handle_request)

            # Now create the page
            page = context.new_page()

            # Prepare execution context with input parameters
            # Include common variables that might be referenced
            exec_globals = {
                "page": page,
                "__builtins__": __builtins__,
                "kwargs": input_params,  # Some code expects kwargs dict
                **input_params
            }

            # The playwright_code is async, so we need to strip await keywords
            sync_code = playwright_code.replace("await ", "")

            # Execute the code
            exec(sync_code, exec_globals, exec_globals)

            # Give some time for final requests to complete
            time.sleep(2)

            browser.close()

        return captured_requests

    except Exception as e:
        print(f"  ❌ Error executing playwright: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================================
# MAIN EXECUTION
# ============================================================================


def phase1_capture_network_logs():
    """Phase 1: Run all Playwright automation and capture network logs"""

    print("=" * 80, flush=True)
    print("PHASE 1: Capturing Network Logs from Playwright", flush=True)
    print("=" * 80, flush=True)

    # Load council extraction results
    print("Loading council_extraction_results.json...", flush=True)
    with open("council_extraction_results.json", "r") as f:
        councils = json.load(f)
    print(f"Loaded {len(councils)} councils", flush=True)

    # Load input.json for test parameters
    print("Loading input.json...", flush=True)
    with open("input.json", "r") as f:
        input_params = json.load(f)
    print(f"Loaded {len(input_params)} council parameters", flush=True)

    # Filter for selenium councils with playwright_code
    print("Filtering for selenium councils...", flush=True)
    selenium_councils = [
        c
        for c in councils
        if c.get("data", {}).get("request_type") == "selenium"
        and c.get("data", {}).get("playwright_code")
    ]

    print(f"Found {len(selenium_councils)} councils using Selenium with playwright_code", flush=True)

    # Track councils without playwright_code
    skipped = [
        c["council"]
        for c in councils
        if c.get("data", {}).get("request_type") == "selenium"
        and not c.get("data", {}).get("playwright_code")
    ]
    if skipped:
        print(f"\n⚠️  Skipping {len(skipped)} councils without playwright_code:")
        for council in skipped[:10]:
            print(f"  - {council}")
        if len(skipped) > 10:
            print(f"  ... and {len(skipped) - 10} more")

    results = []

    for i, council_data in enumerate(selenium_councils, 1):
        council_name = council_data["council"]
        playwright_code = council_data["data"]["playwright_code"]

        print(f"\n[{i}/{len(selenium_councils)}] Processing {council_name}...", flush=True)

        # Get input parameters for this council
        params = input_params.get(council_name, {})

        # Filter out metadata fields
        test_params = {
            k: v
            for k, v in params.items()
            if k not in ["LAD24CD", "url", "wiki_name", "wiki_note", "wiki_command_url_override"]
        }

        if not test_params:
            print(f"  ⚠️  No test parameters found in input.json, skipping")
            results.append(
                {
                    "council": council_name,
                    "status": "skipped",
                    "reason": "no_test_parameters",
                    "network_requests": [],
                }
            )
            continue

        print(f"  Using params: {list(test_params.keys())}")

        # Execute and capture
        network_requests = execute_playwright_and_capture(
            council_name, playwright_code, test_params
        )

        if network_requests is not None:
            print(f"  ✅ Captured {len(network_requests)} network requests")
            results.append(
                {
                    "council": council_name,
                    "status": "success",
                    "playwright_code": playwright_code,
                    "test_params": test_params,
                    "network_requests": network_requests,
                }
            )
        else:
            print(f"  ❌ Failed to capture network requests")
            results.append(
                {
                    "council": council_name,
                    "status": "failed",
                    "playwright_code": playwright_code,
                    "test_params": test_params,
                    "network_requests": [],
                }
            )

    # Save network logs
    with open("playwright_network_logs.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'=' * 80}")
    print(f"PHASE 1 COMPLETE!")
    print(f"Processed: {len(selenium_councils)}")
    print(
        f"Success: {sum(1 for r in results if r['status'] == 'success')}"
    )
    print(f"Failed: {sum(1 for r in results if r['status'] == 'failed')}")
    print(f"Skipped: {sum(1 for r in results if r['status'] == 'skipped')}")
    print(f"Saved to: playwright_network_logs.json")
    print(f"{'=' * 80}")


def main():
    """Run Phase 1: Capture network logs only"""
    print("Script starting...", flush=True)
    phase1_capture_network_logs()
    # Phase 2 will be run separately


if __name__ == "__main__":
    main()
