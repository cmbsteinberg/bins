from pydantic import BaseModel
from typing import List, Optional, Dict, Literal
from enum import Enum
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
