import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

COUNCIL_EXTRACTION_JSON = "extraction/data/council_extraction_results.json"
NETWORK_ANALYSIS_JSON = "extraction/data/network_analysis_results.json"
OUTPUT_DIR = "extraction/data/councils"

# ============================================================================
# CONVERSION FUNCTIONS
# ============================================================================


def merge_council_data(
    extraction_data: Optional[Dict[str, Any]],
    network_data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Merge data from both extraction sources

    Priority:
    - Network analysis data is preferred for api_urls, api_methods (more accurate)
    - Extraction data provides response_format, bin_selector, date_format (parsing info)
    """

    # Start with base from network analysis if available, else extraction
    if network_data:
        analysis = network_data.get("analysis", {})
        base_config = {
            "council": network_data.get("council"),
            "request_type": analysis.get("alternative_request_type"),
            "required_user_input": analysis.get("required_user_input", []),
            "api_urls": analysis.get("api_urls"),
            "api_methods": analysis.get("api_methods"),
            "api_description": analysis.get("api_description"),
        }

        # Add optional network analysis fields
        if analysis.get("api_headers"):
            base_config["api_headers"] = analysis["api_headers"]
        if analysis.get("api_payload_example"):
            base_config["api_payload_example"] = analysis["api_payload_example"]
    else:
        # Use extraction data only
        data = extraction_data.get("data", {})
        base_config = {
            "council": extraction_data.get("council"),
            "request_type": data.get("request_type"),
            "required_user_input": data.get("required_user_input", []),
            "api_urls": data.get("api_urls"),
            "api_methods": data.get("api_methods"),
            "api_description": data.get("api_description"),
        }

    # Add parsing info from extraction data if available
    if extraction_data:
        data = extraction_data.get("data", {})

        if data.get("response_format"):
            base_config["response_format"] = data["response_format"]
        if data.get("bin_selector"):
            base_config["bin_selector"] = data["bin_selector"]
        if data.get("date_format"):
            base_config["date_format"] = data["date_format"]

    return base_config


def convert_json_to_yaml():
    """Convert both JSON files to individual YAML files per council"""

    print("=" * 80)
    print("Converting JSON to YAML files")
    print("=" * 80)

    # Load both input JSON files
    print(f"\nLoading {COUNCIL_EXTRACTION_JSON}...")
    with open(COUNCIL_EXTRACTION_JSON, "r") as f:
        extraction_councils = json.load(f)
    print(f"Loaded {len(extraction_councils)} councils from initial extraction")

    print(f"\nLoading {NETWORK_ANALYSIS_JSON}...")
    with open(NETWORK_ANALYSIS_JSON, "r") as f:
        network_councils = json.load(f)
    print(f"Loaded {len(network_councils)} councils from network analysis")

    # Create lookup dictionaries by council name
    extraction_by_name = {c["council"]: c for c in extraction_councils}
    network_by_name = {c["council"]: c for c in network_councils}

    # Get all unique council names
    all_council_names = set(extraction_by_name.keys()) | set(network_by_name.keys())
    print(f"\nTotal unique councils: {len(all_council_names)}")

    # Categorize councils
    api_ready = []
    selenium_councils = []
    skipped = []

    for council_name in sorted(all_council_names):
        extraction_data = extraction_by_name.get(council_name)
        network_data = network_by_name.get(council_name)

        # Check if selenium in EITHER source
        is_selenium_extraction = (
            extraction_data and
            extraction_data.get("data", {}).get("request_type") == "selenium"
        )
        is_selenium_network = (
            network_data and
            network_data.get("analysis", {}).get("alternative_request_type") == "selenium"
        )

        if is_selenium_extraction or is_selenium_network:
            selenium_councils.append({
                "name": council_name,
                "extraction_data": extraction_data,
                "network_data": network_data,
                "source": "network_analysis" if is_selenium_network else "extraction",
            })
        else:
            # Check if has valid request type
            has_extraction_type = (
                extraction_data and
                extraction_data.get("data", {}).get("request_type") not in [None, "selenium"]
            )
            has_network_type = (
                network_data and
                network_data.get("analysis", {}).get("alternative_request_type") not in [None, "selenium"]
            )

            if has_extraction_type or has_network_type:
                api_ready.append({
                    "name": council_name,
                    "extraction_data": extraction_data,
                    "network_data": network_data,
                })
            else:
                skipped.append(council_name)

    print(f"\nCategories:")
    print(f"  API-ready: {len(api_ready)}")
    print(f"  Selenium (holding patterns): {len(selenium_councils)}")
    print(f"  Skipped (no valid request type): {len(skipped)}\n")

    # Create output directory
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    # Convert API-ready councils to YAML
    api_count = 0
    print("Processing API-ready councils:")
    for council_info in api_ready:
        council_name = council_info["name"]
        config = merge_council_data(
            council_info["extraction_data"],
            council_info["network_data"],
        )

        yaml_file = output_path / f"{council_name}.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        print(f"✅ {council_name}.yaml")
        api_count += 1

    # Create holding patterns for Selenium councils
    selenium_from_network = []
    selenium_from_extraction = []

    print("\nCreating holding patterns for Selenium councils:")
    for council_info in selenium_councils:
        council_name = council_info["name"]
        extraction_data = council_info["extraction_data"]
        network_data = council_info["network_data"]

        # Track which source flagged it as selenium
        if council_info["source"] == "network_analysis":
            selenium_from_network.append(council_name)
        else:
            selenium_from_extraction.append(council_name)

        # Get required inputs from either source
        if network_data:
            analysis = network_data.get("analysis", {})
            required_inputs = analysis.get("required_user_input", [])
            description = analysis.get("api_description") or analysis.get("simplification_notes")
        else:
            data = extraction_data.get("data", {})
            required_inputs = data.get("required_user_input", [])
            description = data.get("api_description")

        # Create minimal config marking it as selenium
        config = {
            "council": council_name,
            "request_type": "selenium",
            "required_user_input": required_inputs,
            "status": "not_implemented",
            "notes": "Requires Playwright/Selenium automation - not yet implemented as HTTP requests",
            "api_description": description,
        }

        yaml_file = output_path / f"{council_name}.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        print(f"⏸️  {council_name}.yaml (selenium - {council_info['source']})")

    # Summary
    print(f"\n{'=' * 80}")
    print(f"Conversion complete!")
    print(f"{'=' * 80}")
    print(f"API-ready: {api_count} councils")
    print(f"Selenium (total): {len(selenium_councils)} councils")
    print(f"  - From network analysis: {len(selenium_from_network)} councils")
    print(f"  - From extraction only: {len(selenium_from_extraction)} councils")
    print(f"Skipped (no valid request type): {len(skipped)} councils")
    print(f"\nOutput directory: {output_path.absolute()}")
    print(f"{'=' * 80}")

    # Log selenium councils from network analysis
    if selenium_from_network:
        print(f"\n{'=' * 80}")
        print("Councils flagged as Selenium from network analysis:")
        print(f"{'=' * 80}")
        for council_name in sorted(selenium_from_network):
            print(f"  - {council_name}")
        print(f"{'=' * 80}")


if __name__ == "__main__":
    convert_json_to_yaml()
