# Full coverage — TODO

## 1. True council mapping — DONE

`lad_lookup.json` is now 361 entries pinned to the distinct LAD codes in
`onspd_postcode_lad.parquet` (363 minus `L99999999`/`M99999999`, which are
Channel Islands/Isle of Man pseudo-codes, not councils), named from ONS
`LAD25NM`, with `govuk_url` from GOV.UK Local Links Manager `LGSL524`
(357 of 361; missing for `E06000063`, `E06000064`, `E06000066`, `W06000024`).
22 codes added, 2 stale retired (`E07000097`, `E07000165`). Ownership split:
`pipeline/data/lad_base.json` (ONS/GOV.UK ground truth) + `scraper_lad_map.json`
(input.json/overrides wiring) → composed into `api/data/lad_lookup.json`.
`scripts/lookup/fetch_latest.sh` version-checks all four sources. See AGENTS.md.

**Left over from the rebuild:**
- `pipeline/data/onspd_postcode_lad.parquet` is stamped `onspd_edition: unknown`
  — the edition of the committed artifact was never recorded. Upstream is now
  `ONSPD_AUG_2026` (ours predates it); the next `fetch_latest.sh` run stamps a
  real edition. `onsud_uprn_postcode.parquet` is unstamped (88MB rewrite, no
  benefit until refetch).
- Orphan scrapers: 29 were wired to no LAD. Resolved by adding 8
  `lad_overrides.json` entries (wired 315 → 321, unwired LADs 46 → 40):
  Basildon `E07000066`, Knowsley `E08000011`, Teignbridge `E07000045`, Epping
  Forest `E07000072` (input.json URL is a third-party portal or, for
  Teignbridge, literally `google.co.uk`, so domain matching couldn't reach the
  scraper); East Herts `E07000242` (recoded); Gosport `E07000088` and Stroud
  `E07000082` (input.json gave Gosport Stroud's `LAD24CD`); Blackburn with
  Darwen `E06000008` (input.json listed Blackburn with **Blaby's** URL, so the
  LAD served Blaby's bin days).
  Remaining ~18 orphans are duplicate hacs/ukbcd/port files for an
  already-wired council — benign, since HACS retention matches on a looser key
  (prefix/name) than wiring (exact domain). `ukbcd_harrogate_borough_council`
  and `ukbcd_eden_district_council` cover fractions of successor authorities
  (North Yorkshire `E06000065`, Westmorland and Furness `E06000064`) and need
  postcode-level sub-routing, not a LAD wire. `ukbcd_environment_first` has no
  `LAD24CD` upstream; Lewes and Eastbourne are already wired.
- 40 LADs still have no scraper — see §2.

## 1a. Original analysis (kept for context)

**Problem:** `lad_lookup.json` (343) built from `input.json` LAD24CD. Not ground truth — we don't know what we don't know.

**Pin to latest codes via UPRN table (correct):**
- `pipeline/data/onspd_postcode_lad.parquet` (363 distinct `oslaua` incl. L/M) + `onsud_uprn_postcode.parquet` is the source for `api/data/postcode_lookup.parquet` — this is what `/council/{postcode}` actually resolves (`api/services/council_lookup.py:84`). It is newer than `LAD_MAY_2025` boundaries (361) — e.g. it has `E07000242` (East Herts new) not `E07000097` (old), but still `E08000016/19` not `E08000038/39` (Boundary/ONSPD lag).
- **Decision:** pin `lad_lookup` to **ONSPD+ONSUD distinct codes** (363 incl. 2 non-UK) + **GOV.UK Local Links Manager** `LGSL524/LGIL8` (355 GSS→rubbish URL) as URL source. Boundary file only for `coverage.geojson` map, not for lookup. Store ONSPD version in parquet metadata and update monthly.
- **We don't have this yet:** `scripts/lookup/create_lookup_table.py:17` is manual (`Download ONSPD multi_csv zip, unzip, and run COPY ...`). Ideally add `scripts/lookup/fetch_latest.sh` to `curl` latest ONSPD (ONS Geoportal), ONSUD, LAD boundaries (`LAD_MAY_2025_UK_BUC` `scripts/coverage/generate_coverage_map.py:10`), and GOV.UK CSV in one go — then `uv run python -m scripts.lookup.create_lookup_table` is a true one-liner.
  - *Note:* ONSPD zip is `~2.3GB` (Nov 2025, growing) — `duckdb` can't slim the download (still has to pull `Data/multi_csv/*.csv`). Script should version-check (`ETag`/`.upstream_version` + `curl -z`) and cache `~/ONSPD_*` in CI, so we keep committed `15MB` `onspd_postcode_lad.parquet` as artifact and only re-download when ONS cuts a new month.

**Gap:** 22 in parquet not in `lad_lookup` (Rutland E06000017, Southend E06000033, Westminster E09000033 etc — all have GOV.UK URLs), 2 stale in `lad_lookup` not in parquet (E07000097, E07000165), 26 null scrapers all have GOV.UK deeplinks.

**Do:**
- Regenerate `lad_lookup.json` from `363` parquet codes + GOV.UK URL, then attach `scraper_id` from `input.json`/`lad_overrides.json`.
- Add 22, retire 2 stale (Harrogate now N.Yorks E06000065, East Herts already E07000242 in parquet).

## 2. 100% on existing coverage

**Current:** 682/728 cases pass, 46 fails = 31 councils (295/317 badge).

**Do:**
- **Sync blocker:** latest HACS sources import `Icons`, but our compat sync does
  not copy/export `icons.py`; add it, then regenerate and test the recovered scrapers.
- **7 partials** (bedford, eastherts, enfield, harlow, kirklees, reigate, st_helens): refresh stale `TEST_CASES` UPRN via `enrich_test_postcodes.py`.
- **9 hacs dead + 11 ukbcd dead:** `curl_cffi` for Cloudflare, else `routing.json` fallback.
- **4 port regressions** (hillingdon, north_devon, northumberland, three_rivers): re-run `capture_upstream_xhrs.py`.
- **26 null:** re-run XHR capture; port ~10 `httpx_convertible`, **deeplink is correct** for ~5 JS-only (Mendix/Salesforce/Jadu) via GOV.UK URL — return `{deeplink}` not 404.
