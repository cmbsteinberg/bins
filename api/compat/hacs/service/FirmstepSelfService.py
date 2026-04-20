"""Firmstep Self-Service shared helpers (async httpx)."""

import json

import httpx
from bs4 import BeautifulSoup


async def get_hidden_form_inputs(
    session: httpx.AsyncClient, form_url: str, timeout: int = 30
) -> dict:
    r = await session.get(form_url, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    return {
        inp["name"]: inp.get("value", "")
        for inp in soup.find_all("input", type="hidden")
        if inp.get("name")
    }


async def get_verification_token(
    session: httpx.AsyncClient, form_url: str, timeout: int = 30
) -> str:
    inputs = await get_hidden_form_inputs(session, form_url, timeout=timeout)
    token = inputs.get("__RequestVerificationToken")
    if not token:
        raise ValueError(
            f"__RequestVerificationToken not found in form response from {form_url}"
        )
    return token


async def lookup_addresses(
    session: httpx.AsyncClient,
    lookup_url: str,
    postcode: str,
    *,
    search_nlpg: str = "True",
    timeout: int = 30,
) -> dict:
    r = await session.post(
        lookup_url,
        data={"query": postcode, "searchNlpg": search_nlpg, "classification": ""},
        timeout=timeout,
    )
    r.raise_for_status()
    raw = json.loads(r.text)
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, list):
        return {
            item["Key"]: item["Value"]
            for item in raw
            if isinstance(item, dict) and "Key" in item and "Value" in item
        }
    return {}
