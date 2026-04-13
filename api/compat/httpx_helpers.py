"""Helpers for one-shot httpx requests that properly close the client."""

from __future__ import annotations

from typing import Any

import httpx


async def request(method: str, url: str, **kwargs: Any) -> httpx.Response:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        return await client.request(method, url, **kwargs)


async def get(url: str, **kwargs: Any) -> httpx.Response:
    return await request("GET", url, **kwargs)


async def post(url: str, **kwargs: Any) -> httpx.Response:
    return await request("POST", url, **kwargs)


async def put(url: str, **kwargs: Any) -> httpx.Response:
    return await request("PUT", url, **kwargs)


async def delete(url: str, **kwargs: Any) -> httpx.Response:
    return await request("DELETE", url, **kwargs)


async def options(url: str, **kwargs: Any) -> httpx.Response:
    return await request("OPTIONS", url, **kwargs)
