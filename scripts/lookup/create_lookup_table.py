import json
import logging
import time
from pathlib import Path
from urllib.parse import urlparse

import duckdb
import httpx

PARQUET_MAX_AGE_DAYS = 30

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ONS_URL = "https://hub.arcgis.com/api/v3/datasets/7efd49be24fb4ed8b21eedeb2540ea8c_0/downloads/data?format=csv&spatialRefId=4326&where=1%3D1"
INPUT_JSON_URL = "https://raw.githubusercontent.com/robbrad/UKBinCollectionData/master/uk_bin_collection/tests/input.json"

ROOT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ROOT_DIR / "api" / "data"
SCRAPER_LOOKUP_PATH = DATA_DIR / "admin_scraper_lookup.json"
POSTCODE_PARQUET_PATH = DATA_DIR / "postcode_lookup.parquet"
LAD_LOOKUP_PATH = DATA_DIR / "lad_lookup.json"


def get_domain(url: str) -> str | None:
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    domain = urlparse(url).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


async def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load admin_scraper_lookup.json
    logger.info("Loading admin_scraper_lookup.json")
    with open(SCRAPER_LOOKUP_PATH) as f:
        domain_to_scraper = json.load(f)

    # 2. Fetch input.json and build LAD -> Council mapping
    logger.info("Fetching input.json")
    async with httpx.AsyncClient() as client:
        resp = await client.get(INPUT_JSON_URL)
        resp.raise_for_status()
        input_data = resp.json()

    lad_to_council = {}
    for key, council in input_data.items():
        lad_codes = []
        if "LAD24CD" in council:
            lad_codes.append(council["LAD24CD"])
        if "supported_councils_LAD24CD" in council:
            lad_codes.extend(council["supported_councils_LAD24CD"])

        if not lad_codes:
            continue

        name = council.get("wiki_name") or key
        url = council.get("url")
        domain = get_domain(url)
        scraper_id = domain_to_scraper.get(domain)

        for lad in lad_codes:
            if lad not in lad_to_council or (
                not lad_to_council[lad]["scraper_id"] and scraper_id
            ):
                lad_to_council[lad] = {
                    "name": name,
                    "scraper_id": scraper_id,
                    "url": url,
                }

    logger.info("Found %d LAD mappings", len(lad_to_council))
    with open(LAD_LOOKUP_PATH, "w") as f:
        json.dump(lad_to_council, f, indent=2)

    # 3. Download ONS CSV and convert to Parquet via DuckDB (cached for 30 days)
    if POSTCODE_PARQUET_PATH.exists():
        age_days = (time.time() - POSTCODE_PARQUET_PATH.stat().st_mtime) / 86400
        if age_days < PARQUET_MAX_AGE_DAYS:
            logger.info(
                "Postcode parquet is %.0f days old (max %d), skipping ONS download",
                age_days,
                PARQUET_MAX_AGE_DAYS,
            )
            return

    csv_file = ROOT_DIR / "ons_postcodes.csv"
    logger.info("Downloading ONS CSV (this may take a while)")
    async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
        async with client.stream("GET", ONS_URL) as response:
            response.raise_for_status()
            with open(csv_file, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)

    logger.info("Processing CSV with DuckDB")
    con = duckdb.connect()

    # Find the LAD column name (changes with ONS releases, e.g. LAD24CD, LAD25CD)
    cols = [
        row[0]
        for row in con.execute(
            f"SELECT column_name FROM (DESCRIBE SELECT * FROM '{csv_file}')"
        ).fetchall()
    ]
    lad_col = next(
        (c for c in cols if c.lower().startswith("lad") and c.lower().endswith("cd")),
        None,
    )
    if not lad_col:
        logger.error("Could not find LAD column in header: %s", cols)
        csv_file.unlink()
        return

    logger.info("Using LAD column: %s", lad_col)

    con.execute(
        f"""
        COPY (
            SELECT DISTINCT
                upper(replace(pcds, ' ', '')) AS postcode,
                {lad_col} AS lad_code
            FROM '{csv_file}'
        ) TO '{POSTCODE_PARQUET_PATH}' (FORMAT PARQUET)
        """
    )
    csv_file.unlink()
    logger.info("Done!")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
