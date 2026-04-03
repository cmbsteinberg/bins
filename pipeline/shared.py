"""Shared utilities for the hacs and ukbcd pipeline scripts."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

# Paths
PIPELINE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PIPELINE_DIR.parent
API_DIR = PROJECT_ROOT / "api"
SCRAPERS_DIR = API_DIR / "scrapers"
ADMIN_LOOKUP_PATH = API_DIR / "data" / "admin_scraper_lookup.json"
OVERRIDES_PATH = PIPELINE_DIR / "overrides.json"

# Overly broad domains that should never be used as lookup keys
BLOCKED_DOMAINS = {
    "gov.uk",
    "calendar.google.com",
    "www.gov.uk",
}


def normalise_domain(url: str) -> str:
    """Extract bare domain from a URL."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    domain = urlparse(url).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def load_admin_lookup() -> dict[str, str]:
    """Load the admin_scraper_lookup.json mapping."""
    if not ADMIN_LOOKUP_PATH.exists():
        return {}
    return json.loads(ADMIN_LOOKUP_PATH.read_text())


def save_admin_lookup(lookup: dict[str, str]) -> None:
    """Save the admin_scraper_lookup.json mapping."""
    ADMIN_LOOKUP_PATH.write_text(json.dumps(lookup, indent="\t", sort_keys=True))


def load_overrides() -> dict:
    """Load the pipeline overrides config."""
    if not OVERRIDES_PATH.exists():
        return {}
    return json.loads(OVERRIDES_PATH.read_text())
