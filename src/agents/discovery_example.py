"""
Example script demonstrating the bin API discovery workflow.

This shows how Claude Agent SDK would use chrome-ws directly (via bash)
combined with the network analyzer and config generator.

For actual agent implementation, this logic would be in Claude's prompt
and it would execute bash commands directly.
"""

import subprocess
import json
import time
from pathlib import Path
from datetime import datetime

from network_analyzer import NetworkAnalyzer
from config_generator import ConfigGenerator
from models import CouncilDiscovery, APIAnalysis, NetworkRequest


def discover_council_api(
    council_name: str,
    url: str,
    postcode: str,
    output_dir: Path
) -> CouncilDiscovery:
    """
    Discover bin collection API for a single council.

    In a real Claude Agent SDK setup, Claude would:
    1. Read the SKILL.md to understand chrome-ws commands
    2. Execute these bash commands directly
    3. Parse the results and make decisions
    4. Call the analyzer and config generator

    Args:
        council_name: Name of the council
        url: Council website URL
        postcode: Test postcode for that council
        output_dir: Where to save outputs

    Returns:
        CouncilDiscovery object
    """
    print(f"\n{'='*60}")
    print(f"Discovering API for: {council_name}")
    print(f"URL: {url}")
    print(f"Postcode: {postcode}")
    print(f"{'='*60}\n")

    chrome_ws = Path(__file__).parent / "using-chrome-directly" / "chrome-ws"
    network_file = output_dir / f"{_slugify(council_name)}_network.json"

    # Step 1: Start Chrome if not running
    print("1. Starting Chrome with remote debugging...")
    subprocess.run([str(chrome_ws), "start"], capture_output=True)
    time.sleep(1)

    # Step 2: Start network monitoring session
    print("2. Starting network monitoring session...")
    result = subprocess.run(
        [str(chrome_ws), "session-start", "0"],
        capture_output=True,
        text=True
    )
    session_id = result.stdout.strip()
    print(f"   Session ID: {session_id}")

    # Keep session process alive in background
    time.sleep(2)

    try:
        # Step 3: Navigate to council bin lookup page
        print(f"3. Navigating to {url}...")
        subprocess.run(
            [str(chrome_ws), "session-cmd", session_id, "navigate", url],
            capture_output=True,
            timeout=30
        )
        time.sleep(2)

        # Step 4: Find and fill postcode field
        # In real agent: Claude would inspect page and find the right selector
        print(f"4. Looking for postcode input field...")
        print("   (In real agent: Claude inspects DOM to find correct selector)")

        # Common selectors to try
        postcode_selectors = [
            "input#postcode",
            "input[name='postcode']",
            "input[type='text']",
            "input.postcode"
        ]

        filled = False
        for selector in postcode_selectors:
            try:
                print(f"   Trying selector: {selector}")
                subprocess.run(
                    [str(chrome_ws), "session-cmd", session_id, "fill", selector, postcode],
                    capture_output=True,
                    timeout=10,
                    check=True
                )
                print(f"   ✓ Filled postcode using {selector}")
                filled = True
                break
            except:
                continue

        if not filled:
            print("   ✗ Could not find postcode input - manual inspection needed")

        time.sleep(1)

        # Step 5: Click submit/search button
        print("5. Looking for submit button...")
        submit_selectors = [
            "button[type='submit']",
            "button#search",
            "input[type='submit']",
            "button.search"
        ]

        clicked = False
        for selector in submit_selectors:
            try:
                print(f"   Trying selector: {selector}")
                subprocess.run(
                    [str(chrome_ws), "session-cmd", session_id, "click", selector],
                    capture_output=True,
                    timeout=10,
                    check=True
                )
                print(f"   ✓ Clicked submit using {selector}")
                clicked = True
                break
            except:
                continue

        if not clicked:
            print("   ✗ Could not find submit button - manual inspection needed")

        # Step 6: Wait for results
        print("6. Waiting for results to load...")
        time.sleep(5)  # Allow time for API calls to complete

        # Step 7: Stop session and export network log
        print("7. Stopping session and exporting network log...")
        subprocess.run(
            [str(chrome_ws), "session-stop", session_id, str(network_file)],
            capture_output=True,
            timeout=30
        )
        print(f"   ✓ Network log saved: {network_file}")

    except Exception as e:
        print(f"   ✗ Error during discovery: {e}")
        # Try to cleanup session
        subprocess.run(
            [str(chrome_ws), "session-stop", session_id, str(network_file)],
            capture_output=True
        )
        raise

    # Step 8: Analyze network traffic
    print("\n8. Analyzing captured network traffic...")
    with open(network_file) as f:
        network_log = json.load(f)

    print(f"   Total requests captured: {len(network_log)}")

    analyzer = NetworkAnalyzer()
    api_analysis = analyzer.analyze(network_log)

    print(f"\n   API Analysis:")
    print(f"   - URL: {api_analysis.api_url}")
    print(f"   - Method: {api_analysis.method}")
    print(f"   - Confidence: {api_analysis.confidence:.2%}")
    print(f"   - Reasoning: {api_analysis.reasoning}")

    # Step 9: Create discovery object
    discovery = CouncilDiscovery(
        council=council_name,
        url=url,
        postcode_used=postcode,
        visual_data=None,  # Could extract this from page
        network_requests=[NetworkRequest(**req) for req in network_log],
        api_analysis=api_analysis,
        timestamp=datetime.now()
    )

    # Save discovery JSON
    discovery_file = output_dir / f"{_slugify(council_name)}_discovery.json"
    with open(discovery_file, 'w') as f:
        json.dump(discovery.model_dump(mode='json'), f, indent=2, default=str)
    print(f"\n   ✓ Discovery saved: {discovery_file}")

    return discovery


def generate_config_from_discovery(discovery: CouncilDiscovery, output_dir: Path) -> Path:
    """
    Generate YAML config from discovery.

    Args:
        discovery: CouncilDiscovery object
        output_dir: Where to save config

    Returns:
        Path to generated YAML config
    """
    print("\n9. Generating YAML configuration...")

    generator = ConfigGenerator()
    config = generator.generate(discovery.model_dump(mode='json'))

    config_file = output_dir / f"{config['slug']}.yaml"
    generator.save(config, config_file)

    print(f"   ✓ Config saved: {config_file}")
    print(f"\n   Config summary:")
    print(f"   - API endpoint: {config['api']['endpoint']}")
    print(f"   - Confidence: {config['confidence']:.2%}")

    return config_file


def _slugify(text: str) -> str:
    """Convert text to slug."""
    import re
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '_', slug)
    return slug.strip('_')


if __name__ == "__main__":
    """
    Example usage - discover API for a test council.

    In real usage with Claude Agent SDK:
    - Claude would read postcodes_by_council.csv
    - For each council, Claude would execute the chrome-ws commands
    - Claude would parse results and call analyzer/generator
    - All of this would be in Claude's reasoning, not hardcoded
    """

    # Create output directories
    output_dir = Path(__file__).parent.parent.parent / "data" / "discoveries"
    output_dir.mkdir(exist_ok=True, parents=True)

    configs_dir = Path(__file__).parent.parent.parent / "configs"
    configs_dir.mkdir(exist_ok=True, parents=True)

    # Example: Stirling Council (from the CSV data)
    discovery = discover_council_api(
        council_name="Stirling Council",
        url="https://my.stirling.gov.uk/",
        postcode="FK15 0AF",
        output_dir=output_dir
    )

    # Generate config
    config_file = generate_config_from_discovery(discovery, configs_dir)

    print(f"\n{'='*60}")
    print("✓ Discovery complete!")
    print(f"{'='*60}")
    print(f"\nNext steps:")
    print(f"1. Review network log: {output_dir / f'{_slugify(discovery.council)}_network.json'}")
    print(f"2. Review discovery: {output_dir / f'{_slugify(discovery.council)}_discovery.json'}")
    print(f"3. Review config: {config_file}")
    print(f"4. Test API manually with curl using the config")
