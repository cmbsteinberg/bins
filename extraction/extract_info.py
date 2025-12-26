import asyncio
import aiohttp
import json
from enum import Enum
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from google import genai
from google.genai.types import (
    GenerateContentConfig,
    ThinkingConfig,
    ThinkingLevel,
)
from dotenv import load_dotenv
import os

load_dotenv()


# ============================================================================
# STRUCTURED OUTPUT SCHEMA
# ============================================================================


class RequestType(str, Enum):
    """The type of scraping approach used"""

    SINGLE_API = "single_api"  # One HTTP request returns bin data
    TOKEN_THEN_API = "token_then_api"  # Get CSRF token/cookie, then query
    ID_LOOKUP_THEN_API = (
        "id_lookup_then_api"  # Find council ID from postcode, then query
    )
    SELENIUM = "selenium"  # Browser automation (will be converted to Playwright)
    CALENDAR_CALCULATION = "calendar"  # Date arithmetic based on fixed patterns


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"


# Simplified flat schema for faster generation


class CouncilExtraction(BaseModel):
    """Simplified extraction spec for faster generation"""

    council_name: str
    request_type: RequestType
    required_user_input: List[str]

    # Flattened API info (instead of nested objects)
    api_urls: Optional[List[str]] = None  # URLs in sequence
    api_methods: Optional[List[str]] = None  # GET/POST per URL
    api_description: Optional[str] = None  # How the API workflow works

    # Bin parsing (simplified)
    response_format: Optional[Literal["json", "html", "xml"]] = None
    bin_selector: Optional[str] = None  # CSS/JSONPath for bin entries
    date_format: Optional[str] = None  # e.g., "%d/%m/%Y"

    # Calendar (simplified)
    calendar_description: Optional[str] = None  # How dates are calculated
    calendar_interval_days: Optional[int] = None  # 7, 14, etc.

    # Playwright (simplified)
    playwright_steps: Optional[str] = None  # Natural language steps
    playwright_code: Optional[str] = None  # Python async code

    notes: Optional[str] = None


# ============================================================================
# CONFIGURATION
# ============================================================================

GITHUB_API_URL = "https://api.github.com/repos/robbrad/UKBinCollectionData/contents/uk_bin_collection/uk_bin_collection/councils"
INPUT_JSON_URL = "https://raw.githubusercontent.com/robbrad/UKBinCollectionData/refs/heads/master/uk_bin_collection/tests/input.json"
MODEL_ID = "gemini-3-flash-preview"

client = genai.Client(
    vertexai=True,
    project=os.environ.get("PROJECT"),
    location="global",
)


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

            # Call LLM with structured output
            response = await client.aio.models.generate_content(
                model=MODEL_ID,
                contents=prompt,
                config=GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=CouncilExtraction,
                    thinking_config=ThinkingConfig(thinking_level=ThinkingLevel.LOW),
                ),
            )

            extracted = response.parsed.model_dump()

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

        with open("council_extraction_results.json", "w") as f:
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
