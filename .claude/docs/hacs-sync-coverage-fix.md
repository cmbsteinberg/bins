# HACS Sync Coverage Fix

## Date: 2026-04-12

## Problem

We were only syncing **217 of 256** UK scrapers from the upstream HACS repo (`mampfes/hacs_waste_collection_schedule`). Two separate bugs caused 39 scrapers to be missed, meaning we were falling back to lower-quality UKBCD equivalents or having zero coverage for some councils.

## Root Causes

### 1. `sync.sh` pattern too narrow

`pipeline/hacs/sync.sh` line 9 had `PATTERN="*_gov_uk.py"`. This missed **8 UK scrapers** with non-standard suffixes:

| Scraper | Suffix | Councils Covered |
|---------|--------|-----------------|
| `stirling_uk` | `_uk` | Stirling |
| `manchester_uk` | `_uk` | Manchester |
| `binzone_uk` | `_uk` | South Oxfordshire, Vale of White Horse |
| `roundlookup_uk` | `_uk` | Malvern Hills, Wychavon, Worcester City |
| `north_kesteven_org_uk` | `_org_uk` | North Kesteven |
| `biffaleicester_co_uk` | `_co_uk` | Leicester |
| `environmentfirst_co_uk` | `_co_uk` | Eastbourne, Lewes |
| `fccenvironment_co_uk` | `_co_uk` | Harborough, South Hams, West Devon |

Upstream suffix breakdown: 248 `_gov_uk` + 3 `_co_uk` + 1 `_org_uk` + 4 bare `_uk` = 256 total.

### 2. `filter_hacs_scrapers` relied solely on gov.uk URL prefix matching

After sync, `sync_all.py` filtered scrapers by extracting the `*.gov.uk` prefix from each scraper's URL and checking it against prefixes extracted from input.json URLs. This failed for **31 scrapers** because many councils in input.json use non-gov.uk URLs:

- **PowerApps portals**: Bristol (`bristolcouncil.powerappsportals.com`), Basildon (`mybasildon.powerappsportals.com`)
- **fixmystreet**: Merton (`fixmystreet.merton.gov.uk` — prefix extracted as `merton` but the domain structure confused matching)
- **Third-party platforms**: Chorley (`forms.chorleysouthribble.gov.uk` — compound prefix), Cardiff (`www.gov.uk` — too generic)
- **Wrong URL in input.json**: Blackburn's entry pointed to `www.blaby.gov.uk` (a different council entirely)

## Fix Applied

### `pipeline/hacs/sync.sh`

Changed `PATTERN="*_gov_uk.py"` to `UK_PATTERN="*_uk.py"` — a single glob that captures all UK suffixes (`_gov_uk`, `_co_uk`, `_org_uk`, and bare `_uk`). Verified no false positives exist upstream (all `*_uk.py` files are genuinely UK scrapers).

### `pipeline/shared.py`

Added `normalise_council_name()` — normalises CamelCase input.json keys, underscore-separated filenames, and human-readable TITLE strings to the same comparable form:

```
BristolCityCouncil  →  bristol
bristol_gov_uk      →  bristol
Bristol City Council →  bristol
KnowsleyMBCouncil  →  knowsley
```

Strips: domain suffixes (`_gov_uk`, `.co.uk`, etc.), filler words (`council`, `city`, `borough`, `district`, `county`, `metropolitan`, `royal`, `london`, `of`, `and`, `the`, `mb`, `mbc`, `mdc`, `dc`, `bc`), and non-alpha characters. Handles CamelCase splitting including uppercase runs like `MB` in `KnowsleyMBCouncil`.

### `pipeline/sync_all.py`

**`build_needed_prefixes` → `build_needed_identifiers`**: Now builds identifiers from three sources per input.json entry:
1. **Normalised key name** (most reliable — always present). E.g. `BristolCityCouncil` → `bristol`
2. **gov.uk prefix from URL** (as before). E.g. `https://sutton.gov.uk` → `sutton`
3. **Domain-based heuristic** for non-gov URLs — strips common prefixes (`my`, `online`, `apps`, `forms`, `waste`, `maps`) from the first domain label. E.g. `mybasildon.powerappsportals.com` → `basildon`

This produces ~430 identifiers from ~334 input.json entries (vs ~301 pure gov.uk prefixes before).

**`filter_hacs_scrapers`**: Now matches each HACS scraper against `needed_ids` using three strategies:
1. **gov.uk prefix** from the scraper's `URL` constant
2. **Normalised filename** (strip `hacs_` prefix + domain suffix)
3. **Normalised `TITLE`** constant from scraper source (catches `biffaleicester_co_uk` whose TITLE is "Leicester City Council")

## Results

### Now kept (30 scrapers previously missing)

These HACS scrapers will now survive filtering, replacing lower-quality UKBCD equivalents where they exist:

| HACS Scraper | Was using instead | Match strategy |
|---|---|---|
| `basildon_gov_uk` | `ukbcd_basildon_council` | fname=basildon |
| `biffaleicester_co_uk` | `ukbcd_leicester_city_council` | title=leicester |
| `blackburn_gov_uk` | *(none — input.json URL is wrong)* | fname=blackburn |
| `bristol_gov_uk` | `ukbcd_bristol_city_council` | fname=bristol |
| `cardiff_gov_uk` | `ukbcd_cardiff_council` | fname=cardiff |
| `cheshire_east_gov_uk` | `ukbcd_cheshire_east_council` | fname=cheshireeast |
| `chorley_gov_uk` | `ukbcd_chorley_council` | fname=chorley |
| `dudley_gov_uk` | `ukbcd_dudley_council` | fname=dudley |
| `eastherts_gov_uk` | *(none)* | fname=eastherts |
| `environmentfirst_co_uk` | `ukbcd_environment_first` | fname=environmentfirst |
| `gwynedd_gov_uk` | `ukbcd_gwynedd_council` | fname=gwynedd |
| `hounslow_gov_uk` | `ukbcd_london_borough_hounslow` | fname=hounslow |
| `knowsley_gov_uk` | `ukbcd_knowsley_m_b_council` | fname=knowsley |
| `lancaster_gov_uk` | `ukbcd_lancaster_city_council` | fname=lancaster |
| `lisburn_castlereagh_gov_uk` | `ukbcd_lisburn_castlereagh_city_council` | fname=lisburncastlereagh |
| `maldon_gov_uk` | `ukbcd_maldon_district_council` | fname=maldon |
| `manchester_uk` | `ukbcd_manchester_city_council` | fname=manchester |
| `merton_gov_uk` | `ukbcd_merton_council` | fname=merton |
| `milton_keynes_gov_uk` | `ukbcd_milton_keynes_city_council` | fname=miltonkeynes |
| `north_kesteven_org_uk` | `ukbcd_north_kesteven_district_council` | fname=northkesteven |
| `norwich_gov_uk` | `ukbcd_norwich_city_council` | fname=norwich |
| `stirling_uk` | `ukbcd_stirling_council` | fname=stirling |
| `sutton_gov_uk` | `ukbcd_london_borough_sutton` | fname=sutton |
| `swansea_gov_uk` | `ukbcd_swansea_council` | fname=swansea |
| `teignbridge_gov_uk` | `ukbcd_teignbridge_council` | fname=teignbridge |
| `torridge_gov_uk` | `ukbcd_torridge_district_council` | fname=torridge |
| `waverley_gov_uk` | `ukbcd_waverley_borough_council` | fname=waverley |
| `westsuffolk_gov_uk` | `ukbcd_west_suffolk_council` | fname=westsuffolk |
| `wiltshire_gov_uk` | `ukbcd_wiltshire_council` | fname=wiltshire |
| `wychavon_gov_uk` | `ukbcd_wychavon_district_council` | fname=wychavon |

Note: 9 of these (dudley, hounslow, merton, milton_keynes, sutton, swansea, torridge, westsuffolk, cheshire_east) are in `overrides.json` as explicit HACS→UKBCD fallbacks, so they'll be synced and kept but then overridden. The remaining 21 will actively replace their UKBCD equivalents.

### Correctly filtered out (9 scrapers)

| HACS Scraper | Why no match |
|---|---|
| `allerdale_gov_uk` | Council abolished 2023 (merged into Cumberland). Not in input.json |
| `bridgend_gov_uk` | Not in input.json |
| `chiltern_gov_uk` | Council abolished 2020 (merged into Buckinghamshire). Not in input.json |
| `east_northamptonshire_gov_uk` | Council abolished 2021 (merged into North Northamptonshire). Not in input.json |
| `fccenvironment_co_uk` | Multi-council aggregator (see below). Name doesn't match any council |
| `northherts_gov_uk` | Abbreviation mismatch: `northherts` vs `northhertfordshire` in input.json |
| `richmondshire_gov_uk` | Council abolished 2023 (merged into North Yorkshire). Not in input.json |
| `roundlookup_uk` | Multi-council aggregator (see below). Name doesn't match any council |
| `binzone_uk` | Multi-council aggregator (see below). Name doesn't match any council |

### Bug fix: `scotborders_gov_uk` now correctly filtered

Previously kept by accident — the old filter had `if prefix is None: continue` which kept any scraper with a non-gov.uk URL. Scottish Borders uses `bartecmunicipal.com` and is not in input.json, so it should be filtered. The new multi-strategy matching correctly identifies it has no match.

## HACS Multi-Council Aggregator Scrapers

These scrapers serve multiple councils through a shared backend. They get filtered because their names (`binzone`, `roundlookup`, `fccenvironment`) don't match any council in input.json.

### `binzone_uk`
- **Platform**: Shared portal at `eform.southoxon.gov.uk/ebase/BINZONE_DESKTOP.eb`
- **Councils**: South Oxfordshire, Vale of White Horse
- **Current coverage**: Both have UKBCD scrapers (`ukbcd_south_oxfordshire_council`, `ukbcd_valeof_white_horse_council`)

### `roundlookup_uk`
- **Platform**: Shared `roundlookup/HandleSearchScreen` system on different subdomains
- **Councils**: Malvern Hills, Wychavon, Worcester City
- **Current coverage**: All have UKBCD scrapers
- **Note**: Takes a `council` parameter to select which sub-system to query

### `fccenvironment_co_uk`
- **Platform**: FCC Environment waste contractor API
- **Councils**: Harborough, South Hams, West Devon
- **Current coverage**: Harborough and South Hams have UKBCD scrapers. **West Devon has NO scraper and is NOT in input.json** — this is the only council with zero coverage that could be served by an aggregator
- **Note**: Takes a `region` parameter

### `environmentfirst_co_uk`
- **Platform**: Environment First shared portal at `environmentfirst.co.uk`
- **Councils**: Eastbourne, Lewes
- **Current coverage**: Both have UKBCD scrapers. Also matched by filename normalisation so **this one is actually kept** by the new filter
- **Note**: `biffaleicester_co_uk` (Leicester) is also kept via TITLE matching

### Comparison with UKBCD aggregators

UKBCD already has the same pattern: `GooglePublicCalendarCouncil` serves ~18 councils (Trafford, Clackmannanshire, Havant, etc.) via Google Calendar ICS feeds. It uses `supported_councils` and `supported_councils_LAD24CD` fields in input.json for routing.

### Future work

Wiring up the HACS aggregators would require:
1. Parsing `EXTRA_INFO` from scraper source to discover sub-councils
2. Mapping sub-council domains to the aggregator scraper ID in `admin_scraper_lookup.json`
3. Handling the extra params (`region`, `council`) in routing
4. Deciding priority: aggregator vs individual scraper when both exist

Not done in this change — all sub-councils except West Devon already have working scrapers.

## Known Limitations

- **northherts_gov_uk**: Abbreviation mismatch (`northherts` vs `northhertfordshire`) means it's filtered despite having a match in input.json (`NorthHertfordshireDistrictCouncil`). The UKBCD scraper covers it. Prefix matching was considered but rejected due to false positives (e.g. `richmondshire` matching `richmond` which is a completely different council).
- **blackburn_gov_uk**: Will be synced and kept by filename match, but the input.json URL for `BlackburnCouncil` erroneously points to `www.blaby.gov.uk`. The HACS scraper may or may not work correctly — depends on whether routing sends traffic to it.
- **Aggregator routing**: The 3 filtered aggregators (`binzone`, `roundlookup`, `fccenvironment`) could provide higher-quality coverage for ~8 councils, but require parameter-based routing that doesn't exist yet.
