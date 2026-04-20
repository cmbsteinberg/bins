"""AchieveForms (Firmstep) shared session and lookup helpers (async httpx)."""

import time

import httpx


async def init_session(
    session: httpx.AsyncClient,
    initial_url: str,
    auth_url: str,
    hostname: str,
    *,
    auth_test_url: str | None = None,
    timeout: int = 30,
) -> str:
    r = await session.get(initial_url, timeout=timeout)
    r.raise_for_status()

    params: dict[str, str] = {
        "uri": str(r.url),
        "hostname": hostname,
        "withCredentials": "true",
    }
    r = await session.get(auth_url, params=params, timeout=timeout)
    r.raise_for_status()
    sid: str = r.json()["auth-session"]

    if auth_test_url is not None:
        params_test: dict[str, str | int] = {
            "sid": sid,
            "_": int(time.time() * 1000),
        }
        r = await session.get(auth_test_url, params=params_test, timeout=timeout)
        r.raise_for_status()

    return sid


async def run_lookup(
    session: httpx.AsyncClient,
    api_url: str,
    sid: str,
    lookup_id: str,
    form_values: dict,
    *,
    timeout: int = 30,
    no_retry: str = "false",
    app_name: str = "AF-Renderer::Self",
) -> dict:
    params: dict[str, str | int] = {
        "id": lookup_id,
        "repeat_against": "",
        "noRetry": no_retry,
        "getOnlyTokens": "undefined",
        "log_id": "",
        "app_name": app_name,
        "_": int(time.time() * 1000),
        "sid": sid,
    }
    r = await session.post(
        api_url,
        params=params,
        json={"formValues": form_values},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()
