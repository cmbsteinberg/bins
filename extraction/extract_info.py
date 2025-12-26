import asyncio
import aiohttp
import json
from dotenv import load_dotenv
from structured_output import CouncilExtraction
from gemini import llm_call_with_struct_output

load_dotenv()


# ============================================================================
# CONFIGURATION
# ============================================================================

GITHUB_API_URL = "https://api.github.com/repos/robbrad/UKBinCollectionData/contents/uk_bin_collection/uk_bin_collection/councils"
INPUT_JSON_URL = "https://raw.githubusercontent.com/robbrad/UKBinCollectionData/refs/heads/master/uk_bin_collection/tests/input.json"


# ============================================================================
# PROCESSING FUNCTIONS
# ============================================================================


async def fetch_input_json(session: aiohttp.ClientSession) -> dict:
    """Fetch the test input.json to validate against"""
    async with session.get(INPUT_JSON_URL) as resp:
        if resp.status != 200:
            print("⚠️  Failed to fetch input.json")
            return {}
        text = await resp.text()
        return json.loads(text)


async def process_council(
    session: aiohttp.ClientSession,
    council_file: dict,
    semaphore: asyncio.Semaphore,
    input_json: dict,
):
    file_name = council_file["name"]
    council_name = file_name.replace(".py", "")
    download_url = council_file["download_url"]

    async with semaphore:
        try:
            # Download source code
            async with session.get(download_url) as resp:
                if resp.status != 200:
                    return None
                code_content = await resp.text()

            # Get expected inputs from input.json for validation
            expected_inputs = input_json.get(council_name, {})
            expected_fields = [
                k
                for k in expected_inputs.keys()
                if k
                not in [
                    "LAD24CD",
                    "url",
                    "wiki_name",
                    "wiki_note",
                    "wiki_command_url_override",
                ]
            ]

            prompt = f"""Extract bin collection workflow for {council_name}.

Expected inputs: {expected_fields}

Classify request_type as:
- single_api (one API call)
- token_then_api (get token, then query)
- id_lookup_then_api (postcode→ID, then query)
- selenium (browser - convert to Playwright)
- calendar (date math only)

Extract: URLs, methods, selectors, date formats, Playwright code if needed.

IMPORTANT: If you provide playwright_code, it MUST be Python code using async/await syntax.
DO NOT use JavaScript syntax (const, let, var). Use Python syntax with await.

CODE:
{code_content}
"""
            extracted = llm_call_with_struct_output(
                prompt=prompt,
                response_schema=CouncilExtraction,
            )
            # Validate against input.json
            extracted_inputs = set(extracted.get("required_user_input", []))
            expected_inputs_set = set(expected_fields)

            if extracted_inputs != expected_inputs_set:
                print(
                    f"⚠️  {council_name}: Input mismatch - expected {expected_inputs_set}, got {extracted_inputs}"
                )
            else:
                print(f"✅ {council_name}")

            return {
                "council": council_name,
                "data": extracted,
                "validation": {
                    "expected_inputs": expected_fields,
                    "extracted_inputs": list(extracted_inputs),
                    "match": extracted_inputs == expected_inputs_set,
                },
            }

        except Exception as e:
            print(f"❌ {council_name}: {str(e)}")
            return None


async def main():
    semaphore = asyncio.Semaphore(50)

    async with aiohttp.ClientSession() as session:
        print("Fetching input.json for validation...")
        input_json = await fetch_input_json(session)
        print(f"Loaded {len(input_json)} council configs from input.json\n")

        print("Fetching council scripts from GitHub...")
        async with session.get(GITHUB_API_URL) as resp:
            if resp.status != 200:
                print("Failed to access GitHub")
                return
            files = await resp.json()

        python_files = [f for f in files if f["name"].endswith(".py")]
        print(f"Starting async extraction for {len(python_files)} scripts...\n")

        tasks = [
            process_council(session, f, semaphore, input_json) for f in python_files
        ]
        results = await asyncio.gather(*tasks)

        # Filter and save
        final_results = [r for r in results if r is not None]

        # Summary stats
        total = len(final_results)
        matched = sum(
            1 for r in final_results if r.get("validation", {}).get("match", False)
        )

        with open("data/council_extraction_results.json", "w") as f:
            json.dump(final_results, f, indent=2)

        print(f"\n{'=' * 60}")
        print(f"🚀 Completed! Saved {total} extractions")
        if total > 0:
            print(
                f"✅ Validation matched: {matched}/{total} ({matched / total * 100:.1f}%)"
            )
        else:
            print("⚠️  No extractions succeeded")
        print("📄 Output: council_extraction_results.json")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
