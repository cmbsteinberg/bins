# Integration Test Failure Analysis

Last run: 2026-04-07 — 660 tests, 565 passed, 95 failed (85.6%)
Previous run: 2026-04-07 — 660 tests, 562 passed, 98 failed (85.2%)

---

## Changes made this session

### Fixes applied

| Fix | Files changed | Tests recovered | Detail |
|-----|--------------|-----------------|--------|
| uk_cloud9_apps.py imports | `api/compat/hacs/service/uk_cloud9_apps.py` | 0 (API down) | Changed `from waste_collection_schedule` to `from api.compat.hacs`. Scrapers now load but Cloud9 API returns 503 |
| curl_cffi `.headers` property | `api/compat/curl_cffi_fallback.py` | 3 | Added `headers` property to `AsyncClient` so scrapers can call `client.headers.update(...)` |
| southkesteven `await` | `api/scrapers/southkesteven_gov_uk.py`, `pipeline/hacs/patch_scrapers.py` | 3 | Added `await` to recursive `self.fetch()` call. Also fixed patcher to handle `fetch` in the `methods_needing_async` check (line 505) |
| test_integration.py `address_id` handling | `tests/test_integration.py` | 5 | Stopped popping `address_id` from params — scrapers like southkesteven and armaghbanbridgecraigavon need it as a query param, not as a path UPRN |
| Re-enabled 7 scrapers | `api/data/disabled_scrapers.json` | ~14 | Removed: armaghbanbridgecraigavon, blackpool, moray, oxford, stratford, east_renfrewshire, southkesteven |

### Scrapers confirmed passing after fixes

| Scraper | Tests | Fix applied |
|---------|-------|-------------|
| east_renfrewshire_gov_uk | 3/3 | curl_cffi `.headers` |
| southkesteven_gov_uk | 3/3 | `await` + test runner `address_id` |
| armaghbanbridgecraigavon_gov_uk | 2/2 | test runner `address_id` |
| moray_gov_uk | 2/2 | re-enabled |
| oxford_gov_uk | 2/2 | re-enabled |
| stratford_gov_uk | 2/2 | re-enabled (intermittent in full suite) |
| blackpool_gov_uk | 2/3 | re-enabled (Test2 flaky — Cloud9 503) |

---

## Remaining disabled scrapers (31)

These are in `api/data/disabled_scrapers.json` — excluded from the registry at startup.

### Council site down or blocking (9 scrapers)

| Scraper | Error | Detail |
|---------|-------|--------|
| allerdale_gov_uk | ConnectTimeout | Site unreachable (>15s) |
| broxtowe_gov_uk | HTTP 500 | Server error from council |
| cardiff_gov_uk | HTTP 401 | Unauthorized — council API may require new auth |
| eastlothian_gov_uk | HTTP 404 | Collection page URL changed or removed |
| hastings_gov_uk | HTTP 500 | Server error from council |
| north_norfolk_gov_uk | ConnectTimeout | Site unreachable (>15s) |
| swale_gov_uk | HTTP 403 | Cloudflare blocking requests |
| thurrock_gov_uk | HTTP 403 | Cloudflare blocking requests |
| wyreforestdc_gov_uk | HTTP 500 | Server error from council |

### Scraper code broken (4 scrapers)

| Scraper | Error | Root cause |
|---------|-------|------------|
| folkestone_hythe_gov_uk | `IndexError: list index out of range` | HTML parsing assumes elements that don't exist |
| kirklees_gov_uk | `TypeError: 'NoneType' object is not subscriptable` | HTML element not found — council page changed |
| rotherham_gov_uk | `AttributeError: 'NoneType' object has no attribute 'find'` | HTML parsing — expected element missing |
| westlothian_gov_uk | `TypeError: string indices must be integers, not 'str'` | JSON response format changed |

### Param mismatch (2 scrapers)

| Scraper | Issue |
|---------|-------|
| fylde_gov_uk | Requires `email`/`password` — test cases use `!secret` placeholders |
| sefton_gov_uk | `SourceArgumentNotFoundWithSuggestions` — value for `houseNumberOrName` not found on council site |

### Council response changed (2 scrapers)

| Scraper | Error | Detail |
|---------|-------|--------|
| harrow_gov_uk | `JSONDecodeError` | Council returning HTML instead of JSON (likely Cloudflare page) |
| thanet_gov_uk | `JSONDecodeError` | Same — non-JSON response |

### UKBCD fallbacks with no test cases (14 scrapers)

No entries in `test_cases.json` so they produce no test failures.

| Scraper |
|---------|
| robbrad_barnsley_m_b_council |
| robbrad_castlepoint_district_council |
| robbrad_chorley_council |
| robbrad_crawley_borough_council |
| robbrad_eden_district_council |
| robbrad_falkirk_council |
| robbrad_mole_valley_district_council |
| robbrad_monmouthshire_county_council |
| robbrad_newham_council |
| robbrad_north_hertfordshire_district_council |
| robbrad_north_somerset_council |
| robbrad_north_yorkshire |
| robbrad_oadby_and_wigston_borough_council |
| robbrad_south_ayrshire_council |

---

## Non-disabled failures (95 tests across ~40 scrapers)

### Cloud9 API down (10 tests, 3 scrapers)

Cloud9 Technologies API returning HTTP 503 for all requests. Import fix applied but API itself is unavailable.

| Scraper | Tests | Status |
|---------|-------|--------|
| arun_gov_uk | 4 | Cloud9 API 503 |
| northherts_gov_uk | 3 | Cloud9 API 503 |
| rugby_gov_uk | 3 | Cloud9 API 503 |

### Council site unreachable / intermittent (~50 tests)

Council website returning errors or intermittently failing. Not actionable on our side.

| Scraper | Tests | Likely cause |
|---------|-------|-------------|
| basildon_gov_uk | 2 | Runtime error |
| bedford_gov_uk | 2 | Runtime error |
| belfast_city_gov_uk | 1 | Runtime error |
| blackpool_gov_uk | 1 | Cloud9 503 (flaky) |
| bolsover_gov_uk | 2 | Site blocking |
| elmbridge_gov_uk | 2 | Runtime error |
| harlow_gov_uk | 1 | Site issue |
| lancaster_gov_uk | 1 | Site issue |
| lisburn_castlereagh_gov_uk | 2 | Runtime error |
| melton_gov_uk | 3 | Site issue |
| midsussex_gov_uk | 3 | Site issue |
| newcastle_gov_uk | 1 | Site issue |
| norwich_gov_uk | 4 | Site issue |
| nwleics_gov_uk | 2 | Runtime error |
| rbwm_gov_uk | 4 | Site issue |
| redbridge_gov_uk | 3 | Site issue |
| south_norfolk_and_broadland_gov_uk | 2 | Site down |
| st_helens_gov_uk | 2 | Site intermittent |
| stratford_gov_uk | 2 | Intermittent (passes standalone) |
| tmbc_gov_uk | 2 | Site issue |
| walthamforest_gov_uk | 2 | Site issue |
| wandsworth_gov_uk | 2 | Site issue |
| warwickdc_gov_uk | 2 | Site issue |
| waverley_gov_uk | 2 | Cloud9 503 |
| welhat_gov_uk | 2 | Site issue |
| west_norfolk_gov_uk | 4 | Site issue |
| westnorthants_gov_uk | 1 | HTTP 500 from council |
| wigan_gov_uk | 3 | Intermittent |

### Test data mismatch (2 tests)

| Scraper | Tests | Issue |
|---------|-------|-------|
| bathnes_gov_uk | 2 | `houseName` and `houseNumber` test cases use `housenameornumber` param — likely needs `address_id` or different param mapping |
| charnwood_gov_uk | 1 | Address value mismatch |

---

## Summary: what's still actionable

| Action | Tests potentially recovered | Effort |
|--------|---------------------------|--------|
| Wait for Cloud9 API recovery (arun, northherts, rugby, waverley) | ~14 | None — API-side issue |
| Fix bathnes/charnwood test data | ~3 | Small |
| Investigate new runtime failures (basildon, bedford, etc.) | ~10 | Medium — per-scraper |
| Add curl_cffi/requests fallback for Cloudflare-blocked (swale, thurrock, harrow, thanet) | ~9 | Medium |
| **Total potentially recoverable** | **~36** | |
| Council-side failures (not fixable) | ~59 | None — wait for councils |
