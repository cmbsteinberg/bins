# Local Authority Lookup System

This system replaces the external `gov.uk` API dependency for mapping postcodes to Local Authority Districts (LAD) and their corresponding scrapers.

## Components

### 1. Construction Script (`scripts/lookup/create_lookup_table.py`)
A standalone script that builds the local lookup databases:
- Downloads the latest **ONS Postcode Directory (ONSPD)** CSV (~1GB).
- Downloads `input.json` from the `UKBinCollectionData` repository to map LAD codes to scraper identifiers.
- Uses **Ibis/DuckDB** to efficiently read the large CSV, selecting only the `PCDS` and `LADCD` columns.
- Normalizes postcodes (uppercase, no spaces) at the DuckDB level.
- Exports a compact, deduplicated Parquet file (`api/data/postcode_lookup.parquet`).
- Generates `api/data/lad_lookup.json`, mapping LAD codes to council names, homepage URLs, and scraper IDs.

### 2. Address Lookup Service (`api/services/address_lookup.py`)
The production service used by the API:
- **Postcode normalization:** `_normalize_postcode()` strips whitespace and uppercases to match the parquet format. Applied in `get_local_authority()` before querying.
- **Local lookup:** Uses Ibis/DuckDB to query the Parquet file. Queries are sub-millisecond.
- **Metadata mapping:** Resolves the LAD code to council name and `scraper_id` via `lad_lookup.json`.
- **Return type:** `get_local_authority()` always returns `list[LocalAuthority]`. Routes check `len(authorities) == 1` to extract a single council.
- **Scraper resolution:** Routes use `LocalAuthority.slug` (the `scraper_id`) directly — no secondary domain-based lookup needed.
- **Address search:** `search_addresses()` validates postcodes against a regex before sending to the Mid Suffolk API. The request body uses `json.dumps()` (not string interpolation) to prevent injection.
- **Cleanup:** `close()` shuts down both the httpx client and the DuckDB connection.

### 3. Route Integration (`api/routes.py`)
- `/addresses/{postcode}` and `/council/{postcode}` call `get_local_authority()` and use `authorities[0].slug` as the `council_id`.
- The old domain-based scraper resolution (`admin_scraper_lookup.json` loaded at module level, `_homepage_to_scraper_id()`) has been removed from routes. `admin_scraper_lookup.json` is still used during the construction phase in `create_lookup_table.py`.

## Data Files
- `api/data/postcode_lookup.parquet`: Postcode → LAD code lookup (normalized: no spaces, uppercase).
- `api/data/lad_lookup.json`: LAD code → council metadata (name, url, scraper_id).
- `api/data/admin_scraper_lookup.json`: Domain → scraper ID mapping, used only during construction.

## Usage
To update the local databases:
```bash
uv run python scripts/lookup/create_lookup_table.py
```
This downloads the required source files and regenerates the Parquet and JSON files in `api/data/`.
