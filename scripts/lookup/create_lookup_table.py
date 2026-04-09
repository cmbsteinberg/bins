import logging
import time
from pathlib import Path

import duckdb
import httpx

PARQUET_MAX_AGE_DAYS = 30

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ONS_URL = "https://hub.arcgis.com/api/v3/datasets/7efd49be24fb4ed8b21eedeb2540ea8c_0/downloads/data?format=csv&spatialRefId=4326&where=1%3D1"

ROOT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ROOT_DIR / "api" / "data"
POSTCODE_PARQUET_PATH = DATA_DIR / "postcode_lookup.parquet"


async def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Download ONS CSV and convert to Parquet via DuckDB (cached for 30 days)
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
