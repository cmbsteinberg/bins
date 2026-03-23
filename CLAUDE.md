# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UK Bin Collection API — a FastAPI service that scrapes UK council websites to return bin/waste collection schedules. ~240 council scrapers live in `api/scrapers/`, each ported from the Home Assistant waste_collection_schedule project and monkey-patched to work as async API endpoints.

## Commands

```bash
# Run dev server
uv run uvicorn api.main:app --reload

# Run all tests (frontend + scraper integration)
uv run pytest tests/ -v

# Run only frontend/API tests (fast, no external calls)
uv run pytest tests/test_frontend.py -v

# Run scraper integration tests (hits live council sites, slow)
uv run pytest tests/test_api_scrapers.py -v

# Run a single scraper test by keyword
uv run pytest tests/test_api_scrapers.py -v -k "aberdeen"

# Lint Python (ruff — excludes api/scrapers/)
uv run ruff check --fix

# Lint JS/JSON (biome)
npx @biomejs/biome check --write

# Regenerate test_cases.json from scraper TEST_CASES
uv run python scripts/scraper_transformation/generate_test_lookup.py

# Regenerate admin_scraper_lookup.json (council domain → scraper ID mapping)
uv run python scripts/address_lookup/generate_admin_lookup.py

# Docker
docker compose up --build
```

## Architecture

**API layer** (`api/`):
- `main.py` — FastAPI app with lifespan managing `ScraperRegistry`, `AddressLookup`, and optional Redis
- `routes.py` — All endpoints: `/api/v1/addresses/{postcode}`, `/api/v1/council/{postcode}`, `/api/v1/lookup/{uprn}`, `/api/v1/calendar/{uprn}`, `/api/v1/councils`, `/api/v1/health`. Routes are mounted under both `/api` and `/api/v1`
- `services/scraper_registry.py` — Dynamically imports all `api/scrapers/*.py` at startup, introspects `Source.__init__` signatures for required/optional params, and dispatches `await source.fetch()` calls
- `services/address_lookup.py` — Resolves postcodes to addresses (via Mid Suffolk API) and to local authorities (via gov.uk API)
- `services/models.py` — Pydantic response models
- `services/rate_limiting.py` — Redis-backed rate limiter (disabled when no `REDIS_URL`)
- `data/admin_scraper_lookup.json` — Council domain → scraper ID mapping

**Scrapers** (`api/scrapers/`):
- ~240 files, one per council. Each defines `TITLE`, `URL`, `TEST_CASES`, and a `Source` class with `async def fetch() -> list[Collection]`
- Originally synchronous; `scripts/scraper_transformation/patch_scrapers.py` converts them to async (replacing `requests`/`urllib` with `httpx`)
- Excluded from ruff linting (configured in `pyproject.toml`)
- `waste_collection_schedule/` contains shared types (`Collection`) and helpers (`ICS`, `SSLError`)

**Scripts** (`scripts/`):
- `scraper_transformation/` — Tools to patch upstream scrapers for async, generate test cases, sync `.gov.uk` source list
- `address_lookup/` — Generates `admin_scraper_lookup.json` mapping council domains to scraper IDs

**Tests** (`tests/`):
- `test_frontend.py` — Fast unit tests for app startup, pages, CORS, error cases
- `test_api_scrapers.py` — Integration tests that hit live council sites concurrently (20 max). Uses `test_cases.json` generated from scraper `TEST_CASES`
- `conftest.py` — Custom pytest plugin that writes structured results to `test_output.json`
- Tests use `pytest-asyncio` with `loop_scope="session"` and `asgi-lifespan` for managing the FastAPI app

**Infrastructure**: Docker Compose runs the API + Redis + Caddy (reverse proxy) + Uptime Kuma (monitoring). Pre-commit hooks via lefthook run ruff, biome, hadolint, caddy validate, and `.gov.uk` source sync.

## Key Patterns

- Scraper `Source` classes take params like `uprn`, `postcode`, `address` in `__init__` and return `list[Collection]` from `async def fetch()`
- The registry filters params to only those accepted by each scraper's `__init__` signature before invocation
- `admin_scraper_lookup.json` maps council website domains to scraper filenames — used to auto-detect which scraper to use from a postcode lookup
- The `/calendar/{uprn}` endpoint returns iCal format for calendar subscription
