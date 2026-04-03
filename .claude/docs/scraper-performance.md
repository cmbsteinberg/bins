# Scraper Performance Improvements

## Progress summary

| Date | Passing | Total | Rate | Delta |
|------|---------|-------|------|-------|
| Baseline | 539 | 681 | 79.1% | — |
| Round 1 (overrides, requests fallback, UKBCD) | 613 | 783 | 78.3% | +74 passing, +102 new tests |
| Round 2 (curl_cffi, SSL, Session.mount) | 639 | 783 | 81.6% | +26 passing |
| Round 3 (SSL context, UKBCD patcher, HACS revert) | ~667 | 783 | ~85.2% | ~+28 passing |

---

## Round 1 — Patching infrastructure (2026-04-03)

### 1. AST patcher: curl_cffi support

**Problem:** 6 HACS scrapers use `from curl_cffi import requests` upstream. The patcher (`pipeline/hacs/patch_scrapers.py`) only recognised `import requests` and `import cloudscraper`, so these files bypassed the full AST transformation. They ended up referencing `httpx.AsyncClient` without importing httpx, and `fetch()` was left as sync.

**Fix in `pipeline/hacs/patch_scrapers.py`:**
- Added `has_curl_cffi_import` to `_AnalysisResult`
- `_analyse_imports()` now detects `from curl_cffi import requests` → sets `has_requests_import = True`
- `_rewrite_import_from()` replaces the curl_cffi import with `import httpx`
- `_final_requests_cleanup()` strips `impersonate=` kwargs (curl_cffi-specific, unsupported by httpx)

**Affected scrapers:** chichester, east_renfrewshire, eastleigh, gateshead, islington, stockton

### 2. HACS→UKBCD override table

**Problem:** 11 HACS scrapers were failing but had working UKBCD alternatives. The UKBCD sync skipped councils already covered by HACS.

**New file: `pipeline/overrides.json`**
Central config mapping council domains to preferred UKBCD scrapers, with reason and optional `disabled` flag.

**Override table (11 active):**

| Domain | UKBCD scraper | Reason |
|--------|--------------|--------|
| bradford.gov.uk | robbrad_bradford_m_d_c | SSL error |
| newham.gov.uk | robbrad_newham_council | SSL error |
| dudley.gov.uk | robbrad_dudley_council | Unreachable |
| westsuffolk.gov.uk | robbrad_west_suffolk_council | Unreachable |
| hounslow.gov.uk | robbrad_london_borough_hounslow | 404 |
| merton.gov.uk | robbrad_merton_council | 404 |
| sutton.gov.uk | robbrad_london_borough_sutton | 503 |
| swansea.gov.uk | robbrad_swansea_council | 500 server error |
| cheshireeast.gov.uk | robbrad_cheshire_east_council | FileNotFoundError |
| milton-keynes.gov.uk | robbrad_milton_keynes_city_council | ValueError |
| torridge.gov.uk | robbrad_torridge_district_council | ValueError |

### 3. Requests fallback for Cloudflare-blocked scrapers

**New file: `api/compat/requests_fallback.py`**
Drop-in `AsyncClient` replacement matching the httpx API, backed by `requests.Session` + `asyncio.to_thread()`.

**14 scrapers on requests fallback:** allerdale, basingstoke, braintree, calderdale, harrow, north_norfolk, northlanarkshire, northyorks_harrogate, oxford, stratford, sunderland, swale, thurrock, wealden

### 4. UKBCD patcher: missing httpx import

**Fix in `pipeline/ukbcd/patch_scrapers.py`:**
- `convert_requests_to_httpx_sync()` now checks if `httpx.` appears in output without `import httpx`, and injects the import after the last top-level import line.

---

## Round 2 — curl_cffi, SSL, Session.mount (2026-04-03)

### 5. curl_cffi fallback for TLS-fingerprinted scrapers

**Problem:** 6 scrapers were written upstream to use `curl_cffi` for browser TLS fingerprint impersonation (Cloudflare bypass). The requests fallback from Round 1 didn't help because these sites specifically need impersonated TLS handshakes.

**New file: `api/compat/curl_cffi_fallback.py`**
Drop-in `AsyncClient` replacement backed by `curl_cffi.requests.Session` with `impersonate="chrome136"`. Same pattern as `requests_fallback.py` — wraps sync calls in `asyncio.to_thread()`.

**Changes:**
- `pipeline/overrides.json` — added `curl_cffi_fallback` list; moved 6 scrapers out of `requests_fallback`
- `pipeline/hacs/patch_scrapers.py` — added `_apply_curl_cffi_fallback()`, refactored override loading into `_load_overrides()`
- `transform_file()` and `_patch_directory()` now support all three HTTP client backends (httpx, requests, curl_cffi)

**6 scrapers on curl_cffi fallback:** chichester, east_renfrewshire, eastleigh, gateshead, islington, stockton

**Result:** chichester, eastleigh, gateshead, islington, stockton all now pass (+13 tests). east_renfrewshire still fails (AttributeError — scraper code issue, not TLS).

### 6. SSL verify=False for certificate-broken councils

**Problem:** Several councils have broken/self-signed SSL certificates. The HACS patcher's `get_legacy_session()` shim set a custom SSL context but didn't disable certificate verification.

**Changes:**
- `pipeline/overrides.json` — added `ssl_verify_disabled` list
- `pipeline/hacs/patch_scrapers.py` — added `_apply_ssl_verify_disabled()` which injects `verify=False` on all client constructors and replaces `get_legacy_session()` calls with `httpx.AsyncClient(verify=False, follow_redirects=True)`

**3 scrapers on SSL disabled:** aberdeenshire, blackburn, richmondshire

**Result:** All 10 tests now pass (+10 tests recovered).

### 7. UKBCD patcher: Session.mount() and HTTPAdapter

**Problem:** Some UKBCD scrapers use `requests.Session().mount("https://", HTTPAdapter(max_retries=Retry(...)))`. The UKBCD patcher converted `Session()` → `httpx.Client()` but left the `.mount()` calls, which httpx doesn't support. This blocked the sutton override.

**Changes:**
- `pipeline/ukbcd/patch_scrapers.py` — `convert_requests_to_httpx_sync()` now strips `.mount()` calls, `Retry(...)` variable assignments, and `HTTPAdapter`/`urllib3.util.retry` imports
- `pipeline/overrides.json` — removed `disabled` flag from sutton override
- Manually fixed existing `robbrad_london_borough_sutton.py`

**Result:** Sutton override re-enabled (still fails due to council returning 503 — council-side issue).

---

## Round 3 — SSL context preservation, UKBCD patcher fixes, HACS revert (2026-04-03)

### 8. SSL context-aware verify disable

**Problem:** Round 2's `_apply_ssl_verify_disabled` used `_inject_verify_false` which skipped scrapers that already had `verify=<var>` (e.g. `verify=ctx`). Ashford, bradford, and newham HACS scrapers still failed with SSL certificate errors. Additionally, ashford's scraper requires a custom TLS context (`TLSv1.2` + `AES256-SHA256` cipher) — simply replacing `verify=ctx` with `verify=False` discards the cipher configuration and breaks the connection.

**Fix in `pipeline/hacs/patch_scrapers.py`:**
- `_inject_verify_false()` gained a `force` parameter to replace existing `verify=<var>` with `verify=False`
- `_apply_ssl_verify_disabled()` now detects custom `ssl.create_default_context()` calls and injects `ctx.check_hostname = False` + `ctx.verify_mode = ssl.CERT_NONE` into the context, preserving cipher/TLS settings while disabling cert verification. Falls back to plain `verify=False` when no custom context exists.

**Overrides changes:**
- Added `ashford_gov_uk`, `bradford_gov_uk`, `newham_gov_uk` to `ssl_verify_disabled`
- **Reverted** bradford and newham from `hacs_to_ukbcd` overrides back to HACS (SSL now fixed)

**Result:** All 3 SSL scrapers pass (ashford: 3, bradford: 26, newham: 2 collections). Bradford and newham now use HACS instead of UKBCD fallbacks.

### 9. UKBCD patcher: NameError fixes

**Problem:** 21 robbrad scrapers hit `NameError` at runtime. Root causes:
- `requests.request()` not converted (patcher only matched `get|post|put|delete|patch|head`)
- `requests.packages.urllib3.*` references not cleaned up
- `CaseInsensitiveDict` from `requests.structures` not handled
- `import httpx` injection already existed but many files were from pre-fix patcher runs

**Fix in `pipeline/ukbcd/patch_scrapers.py` (`convert_requests_to_httpx_sync`):**
- Added `request` to the HTTP method conversion regex (`requests.request()` → `httpx.request()`)
- Added removal of `requests.packages.urllib3.*` lines (cipher config, etc.)
- Added `CaseInsensitiveDict()` → `{}` conversion with import removal

**Result:** 18 of 21 NameError scrapers now pass. 1 skipped (castlepoint — upstream class parse issue). 2 fail with scraper logic errors (north_somerset, north_yorkshire — HTML/JSON parsing, not import issues).

### 10. UKBCD patcher: response attribute and API fixes

**Problem:** Several robbrad scrapers failed with `AttributeError` or `TypeError` due to `requests` → `httpx` API differences.

**Fix in `pipeline/ukbcd/patch_scrapers.py` (`convert_requests_to_httpx_sync`):**
- `response.ok` → `response.is_success` (httpx has no `.ok` attribute)
- Cookie iteration: `for cookie in r.cookies:` → `for cookie in r.cookies.jar:` (httpx `.cookies` yields strings, `.cookies.jar` yields objects with `.name`/`.value`)
- Positional data arg: `.post(url, data)` → `.post(url, data=data)` (httpx requires keyword)
- `verify=False` hoisted from per-request calls to Client constructor (httpx doesn't support per-request `verify=`)

### 11. UKBCD patcher: class detection fix

**Problem:** `get_class_name()` found the first class in each file. Scrapers like buckinghamshire and newport define a dataclass before `CouncilClass`, so the adapter was instantiating the wrong class (e.g. `BucksInput()` instead of `CouncilClass()`).

**Fix in `pipeline/ukbcd/patch_scrapers.py`:**
- `get_class_name()` now prefers any class inheriting from `AbstractGetBinDataClass`, falling back to the first class only if no subclass is found.

**Result:** Buckinghamshire (5 collections), newport (3), mole_valley (3), south_hams (4), wigan (4), norwich (8), harborough (2) all now pass.

---

## Current failure breakdown (estimated ~116 tests, ~55 unique scrapers)

> Run `uv run pytest tests/test_integration.py -v` to get exact counts.
> Results are written to `tests/integration_output.json` (detailed per-case timing, error grouping)
> and `tests/test_output.json` (pytest-native structured results with failure categories).

### Scraper code errors (~40 tests, ~25 scrapers) — potentially fixable

| Error type | Est. tests | Scrapers | Notes |
|------------|-----------|----------|-------|
| AttributeError | ~10 | blackpool, east_renfrewshire, rotherham, stratford, robbrad_monmouthshire, robbrad_oadby_wigston, robbrad_newham_council | NoneType HTML parsing (council HTML changed), response attrs |
| ValueError | ~11 | belfast, eastlothian, milton_keynes, oxford, robbrad_crawley, robbrad_north_herts, torridge | Data parsing failures |
| JSONDecodeError | ~7 | harrow, robbrad_falkirk, robbrad_south_ayrshire, thanet, robbrad_north_yorkshire | Council returned non-JSON |
| TypeError | ~5 | kirklees, lisburn_castlereagh, westlothian | HACS scraper issues (not UKBCD patcher related) |
| KeyError | ~4 | basildon, elmbridge | Missing expected keys in response data |
| FileNotFoundError | ~4 | cheshire_east | Scraper tries to read a local file |
| Other | ~6 | folkestone_hythe (IndexError), fylde (Exception), swale/thurrock (HTTPError), robbrad_barnsley (ConnectionRefused) | Various |

### Council-side errors (~24 tests, ~15 scrapers) — not fixable

| Error type | Tests | Scrapers |
|------------|-------|----------|
| 500 Internal Server Error | ~10 | broxtowe, hastings, south_norfolk_broadland, swansea, westnorthants, wyreforestdc |
| 503 Service Unavailable | ~2 | sutton |
| 404 Not Found | ~6 | eastlothian, hounslow, merton |
| 401 Unauthorized | ~2 | cardiff |
| 400 Bad Request | ~2 | st_helens |
| ConnectTimeout | ~6 | allerdale, north_norfolk |

### Param mismatches (~11 tests, ~5 scrapers) — fixable

| Scrapers | Tests | Notes |
|----------|-------|-------|
| southkesteven | 3 | Requires `address_id` but test cases only provide uprn/postcode |
| armaghbanbridgecraigavon | 2 | Requires `address_id` but test cases only provide uprn |
| bathnes | 2 | `UPRN must be a positive integer if provided` — test cases pass uprn=0 |
| charnwood | 1 | Address value mismatch in test data |
| sefton | 3 | Missing required parameters |

---

## Next steps

### Short-term (high impact)

1. **Fix param mismatch test cases (~11 tests)** — southkesteven and armaghbanbridgecraigavon require `address_id` but test cases provide `uprn`/`postcode`. Either update test case generation to include `address_id`, or add parameter aliasing in the registry. bathnes test cases pass `uprn=0` which fails validation.

2. **Fix castlepoint class detection** — The upstream CastlepointDistrictCouncil file causes the patcher to fail class detection. Investigate the upstream source structure and fix `get_class_name()` or add a special case.

3. **Audit remaining HACS AttributeError/TypeError scrapers** — blackpool, east_renfrewshire, rotherham, stratford, kirklees, lisburn_castlereagh, westlothian have HACS-side scraper issues (not UKBCD patcher). May need per-scraper fixes or upstream sync.

### Medium-term (moderate effort)

4. **Upstream sync for broken scrapers** — Periodically check dev/main branches of `mampfes/hacs_waste_collection_schedule` and `robbrad/UKBinCollectionData` for fixes to councils that changed their APIs. Integrate into sync.sh with a `--branch` flag.

5. **Runtime scraper fallback** — When a council has both HACS and UKBCD scrapers, try the primary and fall back to the alternative on failure. Requires changes to `scraper_registry.py` to maintain a fallback mapping and retry logic.

6. **Health-based routing** — Use the existing `record_success()`/`record_failure()` tracking in `ScraperRegistry` to automatically prefer the source (HACS vs UKBCD) with better recent success rates, instead of static overrides.

### Long-term (architectural)

7. **Caching layer** — Cache successful scraper responses in Redis with a TTL. Most bin collection schedules don't change more than weekly. Reduces external calls and insulates against transient council outages.

8. **Async connection pooling** — Replace throwaway `httpx.AsyncClient()` instances with a shared client per scraper (or a small pool). Reduces connection overhead and avoids triggering rate limits.

9. **Scraper health dashboard** — Expose per-scraper success/failure rates, last success time, and error categories via an admin endpoint. Makes it easy to spot degradation without running the full integration suite.

---

## Files modified

### Round 1
| File | Change |
|------|--------|
| `pipeline/hacs/patch_scrapers.py` | curl_cffi detection, import rewriting, impersonate stripping, requests fallback post-processing |
| `pipeline/ukbcd/patch_scrapers.py` | Override-aware skip logic, httpx import injection |
| `pipeline/overrides.json` | New — central override config |
| `scripts/generate_admin_lookup.py` | Override-aware lookup generation |
| `api/compat/requests_fallback.py` | New — requests-backed AsyncClient |
| `pyproject.toml` | Added `requests` dependency |
| `api/data/admin_scraper_lookup.json` | Regenerated with overrides |
| `tests/test_cases.json` | Regenerated with UKBCD entries |
| `api/scrapers/*.py` | Regenerated by patchers |

### Round 2
| File | Change |
|------|--------|
| `api/compat/curl_cffi_fallback.py` | New — curl_cffi-backed AsyncClient with TLS impersonation |
| `pipeline/hacs/patch_scrapers.py` | curl_cffi fallback, SSL verify disable, refactored override loading |
| `pipeline/ukbcd/patch_scrapers.py` | Strip `.mount()`, `Retry()`, `HTTPAdapter` imports |
| `pipeline/overrides.json` | Added `curl_cffi_fallback`, `ssl_verify_disabled` lists; enabled sutton; moved 6 scrapers from requests to curl_cffi |
| `api/data/admin_scraper_lookup.json` | Regenerated (sutton override enabled) |
| `api/scrapers/*.py` | Regenerated by patchers |

### Round 3
| File | Change |
|------|--------|
| `pipeline/hacs/patch_scrapers.py` | `_inject_verify_false` force mode; `_apply_ssl_verify_disabled` now injects cert-disable into custom SSL contexts instead of discarding them |
| `pipeline/ukbcd/patch_scrapers.py` | `requests.request()` conversion; `requests.packages.urllib3.*` removal; `CaseInsensitiveDict` → dict; `response.ok` → `is_success`; cookie `.cookies` → `.cookies.jar`; positional data arg → keyword; `verify=` hoisting; `get_class_name()` prefers AbstractGetBinDataClass subclass |
| `pipeline/overrides.json` | Added ashford/bradford/newham to `ssl_verify_disabled`; removed bradford/newham from `hacs_to_ukbcd` (reverted to HACS) |
| `api/data/admin_scraper_lookup.json` | Regenerated (bradford/newham back to HACS) |
| `tests/test_cases.json` | Regenerated |
| `api/scrapers/*.py` | Regenerated by both patchers |

---

## Testing

Integration tests write detailed results to two JSON files:

- **`tests/integration_output.json`** — Written by `test_integration.py`. Contains per-case timing, status codes, error details, and failure groups (grouped by HTTP status/error type). Includes `failure_groups` with `count` and individual `cases` arrays.
- **`tests/test_output.json`** — Written by `conftest.py` pytest plugin. Contains pytest-native structured results with `failure_categories` (grouped by error detail/exception/status code), per-result entries with `council`, `label`, `status`, `duration`.

Run integration tests:
```bash
uv run pytest tests/test_integration.py -v          # all scrapers
uv run pytest tests/test_integration.py -v -k "bradford"  # single scraper
```
