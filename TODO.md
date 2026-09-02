# Full coverage — TODO

## 1. True council mapping — rebuild first

**Problem:** `lad_lookup.json` (343) built from `input.json` LAD24CD. Not ground truth — we don't know what we don't know.

**Pin to latest codes via UPRN table (correct):**
- `pipeline/data/onspd_postcode_lad.parquet` (363 distinct `oslaua` incl. L/M) + `onsud_uprn_postcode.parquet` is the source for `api/data/postcode_lookup.parquet` — this is what `/council/{postcode}` actually resolves (`api/services/council_lookup.py:84`). It is newer than `LAD_MAY_2025` boundaries (361) — e.g. it has `E07000242` (East Herts new) not `E07000097` (old), but still `E08000016/19` not `E08000038/39` (Boundary/ONSPD lag).
- **Decision:** pin `lad_lookup` to **ONSPD+ONSUD distinct codes** (363 incl. 2 non-UK) + **GOV.UK Local Links Manager** `LGSL524/LGIL8` (355 GSS→rubbish URL) as URL source. Boundary file only for `coverage.geojson` map, not for lookup. Store ONSPD version in parquet metadata and update monthly.

**Gap:** 22 in parquet not in `lad_lookup` (Rutland E06000017, Southend E06000033, Westminster E09000033 etc — all have GOV.UK URLs), 2 stale in `lad_lookup` not in parquet (E07000097, E07000165), 26 null scrapers all have GOV.UK deeplinks.

**Do:**
- Regenerate `lad_lookup.json` from `363` parquet codes + GOV.UK URL, then attach `scraper_id` from `input.json`/`lad_overrides.json`.
- Add 22, retire 2 stale (Harrogate now N.Yorks E06000065, East Herts already E07000242 in parquet).

## 2. 100% on existing coverage

**Current:** 682/728 cases pass, 46 fails = 31 councils (295/317 badge).

**Do:**
- **7 partials** (bedford, eastherts, enfield, harlow, kirklees, reigate, st_helens): refresh stale `TEST_CASES` UPRN via `enrich_test_postcodes.py`.
- **9 hacs dead + 11 ukbcd dead:** `curl_cffi` for Cloudflare, else `routing.json` fallback.
- **4 port regressions** (hillingdon, north_devon, northumberland, three_rivers): re-run `capture_upstream_xhrs.py`.
- **26 null:** re-run XHR capture; port ~10 `httpx_convertible`, **deeplink is correct** for ~5 JS-only (Mendix/Salesforce/Jadu) via GOV.UK URL — return `{deeplink}` not 404.
