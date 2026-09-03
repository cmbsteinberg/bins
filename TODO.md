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
- 40 LADs still have no scraper — see §2 (33 after this session's 7 wires).

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

## 2. 100% on existing coverage + 33 scopeless

**Current:** 328/361 wired, badge 295/328; 658/736 cases pass
(live-site 503 flaps move this ±6 run to run — flips never touch the wired set).

**Done since:** Icons sync blocker fixed (`api/compat/hacs/icons.py` +
`pipeline/hacs/sync.sh`); stale UPRNs resampled
(`pipeline/shared/enrich_test_postcodes.py`); XHR recapture for the 4 port
regressions + North Devon AchieveForms rewrite; 7 scopeless wired (321 → 328):
Worthing `E07000229` free via the shared Adur backend (verified with Worthing
UPRNs from the ONSUD/ONSPD join, auto-wires on GOV.UK domain match);
Babergh `E07000200` + Mid Suffolk `E07000203` via two per-LAD Placecube ports
(the shared HACS source is unusable — its required `council` selector collides
with the API's reserved `council` query key; base suppressed via
`routing.json`); Cotswold `E07000079`, Forest of Dean `E07000080`, East Suffolk
`E07000244` restored from `pipeline/upstream` (the pre-fix council filter had
deleted them); Powys `W06000023` via a GOSS Forms port (GET `binday` tokens →
form POST with UPRN alone → `bdl-card` dates).

**Triage rule (port vs deeplink)** — full version + sibling-template table in
`pipeline/ports/README.md`. Deeplink only if all three hold: (1) no *working*
plain-HTTP path (broken HACS / Selenium-only counts as absent); (2) a 30–60
min probe finds no data endpoint (`httpx_convertible: false` means "probe",
never "browser"); (3) stateful proprietary runtime (Mendix, Aura w/o fallback,
captcha/Turnstile) — this gate is the crux. Target selection (council bin page
> GOV.UK page > nothing) is separate; "nothing" (Merthyr `W06000024`, no
GOV.UK URL either) is discovery backlog, still deeplink-shaped, never 404.

**Verdicts from the captured 7:** Brighton = deeplink (Mendix; needs a
`{deeplink}` response — 404 today); Hertsmere + Sevenoaks = Oncreate-family
port pair (token replay, no captcha; Hertsmere's `round-search` needs
round→date mapping); Staffs Moorlands undecided (`bins.*` PublicDashboard SPA,
one more probe for the data endpoint).

**Remaining 33, in order:** Hertsmere/Sevenoaks pair → batch XHR capture over
the 12 never-captured with URLs (Boston — external `mybostonuk.com`, Castle
Point, Chelmsford, Great Yarmouth, Halton, NE Derbyshire, North Norfolk,
Nuneaton, Slough, South Kesteven — `/binday` like Powys, possible GOSS
sibling — Uttlesford on a dedicated `bins.` host, Anglesey) → Staffs probe
alongside → discovery on the 17 no-URL (16 from their GOV.UK start point,
Merthyr manual).

**Still open from before:**
- **7 partials** (bedford, eastherts, enfield, harlow, kirklees, reigate, st_helens): resample done, still flapping — live-site noise vs stale params TBD per council.
- **9 hacs dead + 11 ukbcd dead:** `curl_cffi` for Cloudflare, else `routing.json` fallback.
- **4 port regressions** (hillingdon, north_devon, northumberland, three_rivers): recaptured; hillingdon/north_devon/three_rivers still fail 1 case each, northumberland fixed.
