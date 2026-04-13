# Testing

## Test suite overview

All tests live in `tests/`. Run everything with `uv run pytest tests/ -v`.

| File | What it tests | Speed | When to run |
|------|--------------|-------|-------------|
| `test_ci.py` | Scraper compilation, imports, compat modules, scripts syntax, app boot, registry loading | ~1s | Every commit (lefthook pre-commit) |
| `test_frontend.py` | Landing page, API docs, OpenAPI schema, CORS, error cases, route prefixes | ~1s | Every commit (fast enough) |
| `test_integration.py` | All test cases from `test_cases.json` against live council sites via the full API | ~30-40s | Manual / CI pipeline |
| `test_deploy.py` | Docker Compose stack boots, scrapers load, static files served | ~60s | Before deploy |

### Supporting files

| File | Purpose |
|------|---------|
| `conftest.py` | Pytest plugin — writes structured results to `test_output.json` with failure categorisation |
| `test_cases.json` | Generated from scraper `TEST_CASES` dicts. Regenerate with `uv run python -m pipeline.hacs.generate_test_lookup` and `uv run python -m pipeline.ukbcd.generate_test_lookup` |
| `test_output.json` | Generated — structured JSON summary of last test run (gitignored) |
| `integration_output.json` | Generated — detailed integration test results with timing, failure groups, slowest scrapers (gitignored) |

## test_ci.py — CI smoke tests

~720 tests, ~1 second. Designed as a pre-commit gate to catch regressions.

**What it checks:**

1. **Syntax** — every `api/scrapers/*.py` file parses as valid Python (AST-level, no imports executed)
2. **Imports** — every scraper imports successfully and exposes `Source`, `TITLE`, `URL`, `TEST_CASES`
3. **Compat modules** — all `api/compat/**/*.py` modules import cleanly; key types (`Collection`, `CollectionBase`, `AbstractGetBinDataClass`, etc.) are accessible
4. **Scripts** — all `scripts/**/*.py` files parse as valid syntax
5. **App startup** — FastAPI app boots, responds to `/`
6. **Registry** — at least 95% of scraper files loaded into the registry (a few may fail, but mass failure = broken)
7. **Health endpoint** — returns one entry per loaded scraper

**Lefthook integration:** runs as `ci-tests` command in `lefthook.yaml` pre-commit hook with `-x` (stop on first failure).

## test_frontend.py — API surface tests

7 tests, ~1 second. Tests the web UI and API route structure without hitting any external services.

- Landing page renders with expected elements
- API docs page renders
- OpenAPI schema, Swagger UI, ReDoc all respond
- `/api/v1/councils` returns scrapers, `/api/v1/health` returns entries
- Both `/api` and `/api/v1` prefixes work
- Error cases return correct status codes (404 for unknown council, 422 for missing params)
- CORS headers present

## test_integration.py — full integration tests

~680 tests, ~30-40s. Runs **all** test cases (every entry per scraper, not just the first) against the live API with real network calls.

**Key design choices:**

- All lookups run concurrently via `asyncio.gather` with a semaphore (`MAX_CONCURRENCY=40`)
- Results are cached in a session-scoped fixture — the concurrent batch runs once, then each parametrized test reads from the cache
- Each result captures: status code, elapsed time, response size, response headers, response body preview, collections count/types, and structured error info

**Output file (`integration_output.json`):**

```json
{
  "total_test_cases": 681,
  "passed": 539,
  "failed": 142,
  "pass_rate": "79.1%",
  "timing": {
    "min_s": 0.0,
    "max_s": 32.013,
    "median_s": 12.483,
    "mean_s": 13.613,
    "p95_s": 26.941,
    "total_wall_clock_s": 32.522
  },
  "failure_groups": { ... },
  "slowest_20": [ ... ],
  "all_results": [ ... ]
}
```

**Failure categories (as of 2026-04-03):**

| Category | Count | Cause |
|----------|-------|-------|
| `http_503` — "Council site unreachable" | ~30 | Council website down, moved, or blocking |
| `http_503` — SSL cert failures | ~16 | Expired/self-signed certs on council sites |
| `http_503` — "Scraper error: NameError" | ~18 | Missing variable/import from AST patching |
| `http_503` — "Scraper error: TypeError" | ~7 | Wrong arg types, likely httpx API differences |
| `http_503` — "Scraper error: AttributeError" | ~7 | Missing attribute on httpx response objects |
| `http_503` — "Scraper error: ValueError" | ~7 | Bad data parsing in scrapers |
| `http_422` — Missing params | ~11 | Test cases use `uprn` but scraper expects `address_id` |
| Other (KeyError, IndexError, etc.) | ~10 | Council API changes, empty responses |

## test_deploy.py — Docker smoke tests

3 tests, ~60s. Builds and starts the full Docker Compose stack, waits for health, then verifies:

- Health endpoint responds
- Scrapers loaded in container
- Static files served

Tears down containers after. Run separately: `uv run pytest tests/test_deploy.py -v`.

## conftest.py — structured output plugin

Intercepts pytest results and writes `test_output.json` with:

- Per-test entries: node_id, council, label, status, duration
- For failures: full message, extracted fields (UPRN, status code, error detail, error type), failure category
- Summary: total/passed/failed/skipped counts, failures grouped by category

Parses parametrized test IDs using `|` separator (from `test_integration.py`) or bare names (from `test_ci.py`).

## Lefthook hooks

In `lefthook.yaml` under `pre-commit`:

```yaml
ci-tests:
  tags: test
  glob: "*.py"
  run: uv run pytest tests/test_ci.py -x -q --tb=short
```

Runs in parallel with ruff, biome, docker, and scraper sync checks.
