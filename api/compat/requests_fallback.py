"""
Drop-in async replacement for httpx.AsyncClient backed by requests.Session.

Used for scrapers that get Cloudflare-blocked with httpx but work with
requests (different TLS fingerprint via urllib3). Wraps sync requests
calls in asyncio.to_thread() to maintain async compatibility.

Usage in scrapers (applied by the patcher for flagged files):
    from api.compat.requests_fallback import AsyncClient
    # Then use identically to httpx.AsyncClient
"""

from __future__ import annotations

import asyncio
from typing import Any

import requests as _requests


class Response:
    """Wraps requests.Response to match the httpx.Response interface."""

    def __init__(self, resp: _requests.Response):
        self._resp = resp
        self.status_code: int = resp.status_code
        self.headers = resp.headers
        self.text: str = resp.text
        self.content: bytes = resp.content
        self.url = resp.url
        self.encoding = resp.encoding

    def json(self, **kwargs: Any) -> Any:
        return self._resp.json(**kwargs)

    def raise_for_status(self) -> None:
        self._resp.raise_for_status()


class AsyncClient:
    """Async wrapper around requests.Session matching httpx.AsyncClient API."""

    def __init__(
        self,
        *,
        follow_redirects: bool = True,
        verify: Any = True,
        headers: dict[str, str] | None = None,
        timeout: float | None = 120,
        **kwargs: Any,
    ):
        self._session = _requests.Session()
        self._session.max_redirects = 30 if follow_redirects else 0
        self._allow_redirects = follow_redirects
        self._verify = verify
        self._timeout = timeout
        if headers:
            self._session.headers.update(headers)

    async def get(self, url: str, **kwargs: Any) -> Response:
        return await self._request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> Response:
        return await self._request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> Response:
        return await self._request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> Response:
        return await self._request("DELETE", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> Response:
        return await self._request("PATCH", url, **kwargs)

    async def head(self, url: str, **kwargs: Any) -> Response:
        return await self._request("HEAD", url, **kwargs)

    async def _request(self, method: str, url: str, **kwargs: Any) -> Response:
        # Map httpx kwargs to requests kwargs
        if "follow_redirects" in kwargs:
            kwargs["allow_redirects"] = kwargs.pop("follow_redirects")
        else:
            kwargs.setdefault("allow_redirects", self._allow_redirects)
        kwargs.setdefault("verify", self._verify)
        kwargs.setdefault("timeout", self._timeout)

        resp = await asyncio.to_thread(
            self._session.request, method, url, **kwargs
        )
        return Response(resp)

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        self._session.close()

    def close(self) -> None:
        self._session.close()
