# LAD Lookup Refactor: Eliminate admin_scraper_lookup.json

## Problem

Postcode lookups for councils like Redbridge (E11 2PN) returned "Council may not be supported yet" despite `hacs_redbridge_gov_uk.py` existing. The root cause was domain mismatch during scraper resolution:

- `input.json` listed Redbridge's URL as `https://my.redbridge.gov.uk/RecycleRefuse`
- The hacs scraper declared `URL = "https://redbridge.gov.uk"`
- `admin_scraper_lookup.json` keyed on `redbridge.gov.uk`
- `create_lookup_table.py` extracted domain `my.redbridge.gov.uk` from input.json, failed to match, wrote `scraper_id: null`

## Old Flow

```
1. generate_admin_lookup.py scans api/scrapers/, extracts URL constants
   -> writes domain -> scraper mapping to admin_scraper_lookup.json

2. create_lookup_table.py fetches input.json (has LAD codes + council URLs)
   -> loads admin_scraper_lookup.json
   -> tries to match input.json URL domains against admin_scraper_lookup.json
   -> writes lad_lookup.json with scraper_id (often null due to domain mismatch)
```

The problem: two independent data sources (scraper URL constants vs input.json URLs) don't always agree on domains. Subdomains, alternate URLs, and non-standard domains caused silent failures.

## New Flow

```
1. UKBCD patch step (pipeline/ukbcd/patch_scrapers.py) iterates input.json
   -> For each council, decides: hacs scraper wins, or create ukbcd scraper
   -> At this decision point, we know: the LAD code (from input.json) + the winning scraper
   -> Writes lad_lookup.json directly with the correct scraper_id
```

No intermediate `admin_scraper_lookup.json`. No domain matching for LAD resolution. The scraper_id is recorded at the exact moment the hacs-vs-ukbcd decision is made.

Hacs scraper detection uses `build_hacs_domain_lookup()` from `pipeline/shared.py`, which scans hacs files on disk and builds a domain -> scraper map. Matching uses both exact domain and gov.uk prefix fallback (e.g. `my.redbridge.gov.uk` -> prefix `redbridge` -> matches `redbridge.gov.uk`).

## Files Changed

- `pipeline/shared.py` -- Removed `ADMIN_LOOKUP_PATH`, `load_admin_lookup`, `save_admin_lookup`. Added `LAD_LOOKUP_PATH`, `extract_url_from_scraper`, `build_hacs_domain_lookup`.
- `pipeline/ukbcd/patch_scrapers.py` -- Uses filesystem-based hacs detection. Builds `lad_lookup.json` directly via `_record_lad_mappings()`.
- `pipeline/sync_all.py` -- Removed the two admin lookup regeneration steps. Pipeline is 7 steps instead of 9.
- `scripts/lookup/create_lookup_table.py` -- Now only handles ONS postcode parquet download.
- `pipeline/hacs/sync.sh` -- Removed `generate_admin_lookup` call.

## Dead Code

`scripts/generate_admin_lookup.py` and `api/data/admin_scraper_lookup.json` are no longer used and can be deleted.
