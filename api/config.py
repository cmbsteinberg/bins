"""Centralised configuration loaded from environment variables."""

from __future__ import annotations

import os


def _int_env(key: str, default: int) -> int:
    val = os.getenv(key)
    return int(val) if val else default


# Scraper invocation
SCRAPER_TIMEOUT: int = _int_env("SCRAPER_TIMEOUT", 30)

# Redis cache
CACHE_TTL: int = _int_env("CACHE_TTL", 14 * 3600)  # 14 hours

# Rate limiting
RATE_LIMIT_DAILY: int = _int_env("RATE_LIMIT_DAILY", 100)

# Logging
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")  # "json" or "text"

# Public-facing URLs
BASE_URL: str = os.getenv("BASE_URL", "")
FRONTEND_URL: str = os.getenv("FRONTEND_URL", BASE_URL)

# CORS — defaults to FRONTEND_URL if CORS_ORIGINS not explicitly set
CORS_ORIGINS: list[str] = (
    os.getenv("CORS_ORIGINS", "").split(",")
    if os.getenv("CORS_ORIGINS")
    else [FRONTEND_URL]
    if FRONTEND_URL
    else []
)
