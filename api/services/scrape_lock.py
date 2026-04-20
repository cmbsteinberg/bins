"""Cross-process scrape lock via Redis SET NX.

Shared by the API (inline scrape on cache miss) and the worker (nightly
refresh pass) so the same UPRN isn't scraped twice at the same moment.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

LOCK_TTL_SECONDS = 30


async def acquire(redis_client, uprn: str) -> bool:
    if redis_client is None:
        return True
    try:
        return bool(
            await redis_client.set(
                f"scrape-lock:{uprn}", "1", nx=True, ex=LOCK_TTL_SECONDS
            )
        )
    except Exception:
        logger.warning("Scrape lock acquire failed", exc_info=True)
        return True


async def release(redis_client, uprn: str) -> None:
    if redis_client is None:
        return
    try:
        await redis_client.delete(f"scrape-lock:{uprn}")
    except Exception:
        pass
