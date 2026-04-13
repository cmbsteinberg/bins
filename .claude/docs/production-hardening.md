# Production Hardening Changes (2026-04-04)

Summary of changes made to prepare the API for production deployment.

## 1. CORS Lockdown

**File:** `api/main.py`, `api/config.py`

Previously `allow_origins=["*"]` — any domain could make cross-origin requests. Now restricted to `["https://bins.lovesguinness.com"]` by default, configurable via `CORS_ORIGINS` env var (comma-separated list).

## 2. Rate Limiter Midnight Bug Fix

**File:** `api/services/rate_limiting.py`

`_seconds_until_midnight()` had dead code — an unreachable branch (`if now.hour >= 0` is always true) and an unused `midnight` variable. Simplified to a clean two-line calculation using `timedelta(days=1)`.

## 3. BASE_URL Hardcoded Fallback Removed

**File:** `api/main.py`, `api/config.py`

The sitemap endpoint previously fell back to `https://bins.lovesguinness.com` when `BASE_URL` wasn't set. Now defaults to empty string (relative URLs) with a log warning, so deployments must explicitly set `BASE_URL`.

## 4. Silent Exception Handlers Fixed

**Files:** `api/main.py`, `api/routes.py`

Four bare `except Exception: pass` blocks were silently swallowing errors:
- Redis analytics increment in request middleware → now logs at DEBUG
- Redis cache read failure → now logs at WARNING with key info
- Redis cache write failure → now logs at WARNING with key info
- Redis startup failure already had logging (unchanged)

## 5. Structured JSON Logging

**New file:** `api/logging_config.py`

Added a `JSONFormatter` that emits each log record as a single JSON line with fields: `timestamp`, `level`, `logger`, `message`, plus optional `exception`, `method`, `path`, `status_code`, `duration_ms`, `client_ip`.

Called via `setup_logging()` at app import time. The request middleware now attaches structured `extra` fields for downstream consumption.

Controlled by:
- `LOG_FORMAT` — `json` (default) or `text` (human-readable for local dev)
- `LOG_LEVEL` — standard Python levels, defaults to `INFO`

Noisy libraries (uvicorn.access, httpx, httpcore, ibis) are quieted to WARNING.

## 6. Centralised Configuration

**New file:** `api/config.py`

All previously-hardcoded values are now loaded from environment variables with sensible defaults:

| Env Var | Default | Used By |
|---------|---------|---------|
| `SCRAPER_TIMEOUT` | 30 (seconds) | `scraper_registry.py` |
| `CACHE_TTL` | 50400 (14 hours) | `routes.py` |
| `RATE_LIMIT_DAILY` | 100 | `rate_limiting.py` |
| `LOG_LEVEL` | INFO | `logging_config.py` |
| `LOG_FORMAT` | json | `logging_config.py` |
| `CORS_ORIGINS` | `https://bins.lovesguinness.com` | `main.py` |
| `BASE_URL` | (empty) | `main.py` sitemap |

All are passed through in `docker-compose.yml` with `${VAR:-default}` syntax.

## 7. Metrics Endpoint

**File:** `api/routes.py`

New `GET /api/v1/metrics` endpoint returns:
- `request_counts` — per-path hit counts from Redis
- `scraper_count` — total registered scrapers
- `scraper_health_summary` — count of healthy vs unhealthy scrapers
- `config` — current runtime config values (cache TTL, scraper timeout, rate limit)

## 8. Environment Files

**Files:** `.env`, `.env.example`

- `.env.example` — documents all available env vars with placeholder values (`https://your-domain.com`)
- `.env` — real values for current deployment (gitignored)
- Added `FRONTEND_URL` which `CORS_ORIGINS` falls back to if not explicitly set, keeping CORS and the public URL in sync
- `docker-compose.yml` now passes all config env vars through with `${VAR:-default}` syntax

## Test Updates

**Files:** `tests/conftest.py`, `tests/test_frontend.py`

- `conftest.py` sets `CORS_ORIGINS` and `LOG_FORMAT=text` at test collection time (before app import)
- `test_cors` updated to verify restricted CORS: allowed origin gets header, disallowed origin does not

All 719 tests pass (711 CI smoke + 8 frontend).
