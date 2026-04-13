"""Lightweight shim for uk_bin_collection.uk_bin_collection.get_bin_data.

Provides AbstractGetBinDataClass so RobBrad scrapers can define their
CouncilClass without importing the full upstream package.
"""

import logging
from abc import ABC, abstractmethod

import httpx

_LOGGER = logging.getLogger(__name__)


class AbstractGetBinDataClass(ABC):
    @abstractmethod
    def parse_data(self, page: str, **kwargs) -> dict:
        ...

    @classmethod
    async def get_data(cls, url) -> str:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
            )
        }
        try:
            async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers, timeout=10)
                return resp
        except httpx.HTTPError as err:
            _LOGGER.error(f"Request Error: {err}")
            raise
