import json
import logging
import re
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

COMMON_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36"
    ),
}

POSTCODE_RE = re.compile(
    r"^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$", re.IGNORECASE
)


@dataclass
class AddressQuery:
    number: int | str
    street: str
    postcode: str
    property_name: str = ""

    def serialise(self, ignore_postal: bool = True) -> str:
        return json.dumps({
            "number": self.number,
            "postcode": self.postcode,
            "street": self.street,
            "name": self.property_name,
            "ignorePostal": ignore_postal,
        })


class UPRNLookup:
    """Resolves UPRNs via multiple UK council / OS data services."""

    def __init__(self, min_request_interval: float = 0.5):
        self.client = httpx.Client(timeout=30, headers=COMMON_HEADERS)
        self._min_interval = min_request_interval
        self._last_request: float = 0

    def close(self) -> None:
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- public methods ------------------------------------------------

    def lambeth_address_search(
        self, query: AddressQuery
    ) -> list[dict[str, str]]:
        """LLPG address search used by Lambeth (and similar Whitespace councils)."""
        url = "https://wasteservice.lambeth.gov.uk/LLPG/addressSearch"
        headers = {
            **COMMON_HEADERS,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": "https://wasteservice.lambeth.gov.uk/",
            "X-Requested-With": "XMLHttpRequest",
        }
        resp = self._post(url, headers=headers, data=query.serialise())
        return resp.json()

    def enfield_os_places(self, postcode: str) -> list[dict]:
        """Ordnance Survey Places v2 lookup proxied by Enfield council."""
        self._validate_postcode(postcode)
        url = (
            "https://www.enfield.gov.uk/"
            "_design/integrations/ordnance-survey/places-v2"
        )
        headers = {
            **COMMON_HEADERS,
            "Referer": (
                "https://www.enfield.gov.uk/services/"
                "rubbish-and-recycling/find-my-collection-day"
            ),
        }
        resp = self._get(url, headers=headers, params={"query": postcode})
        return resp.json()

    def os_api_find(
        self, postcode: str, custodian_code: str | None = None
    ) -> list[dict]:
        """Direct Ordnance Survey Places API lookup (LPI dataset)."""
        self._validate_postcode(postcode)
        params: dict[str, str] = {
            "dataset": "LPI",
            "output_srs": "EPSG:4326",
            "maxresults": "100",
            "query": postcode,
        }
        if custodian_code:
            params["fq"] = f"LOCAL_CUSTODIAN_CODE:{custodian_code}"
        url = "https://api.os.uk/search/places/v1/find"
        resp = self._get(url, params=params)
        return resp.json()

    def north_norfolk_uprn(self, postcode: str) -> list[dict[str, str]]:
        """North Norfolk XForms address list lookup."""
        self._validate_postcode(postcode)
        url = (
            "https://forms.north-norfolk.gov.uk/"
            "xforms/AddressSearch/GetAddressList"
        )
        resp = self._get(url, params={"postcode": postcode})
        items = resp.json()
        return [
            {"full_address": item["text"], "uprn": item["value"]}
            for item in items
            if item.get("value") and item["value"] != "0"
        ]

    # -- internals -----------------------------------------------------

    def _validate_postcode(self, postcode: str) -> None:
        if not POSTCODE_RE.match(postcode.strip()):
            raise ValueError(f"Invalid postcode format: {postcode}")

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.monotonic()

    def _get(self, url: str, **kwargs) -> httpx.Response:
        self._rate_limit()
        logger.info("GET %s", url)
        resp = self.client.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    def _post(self, url: str, **kwargs) -> httpx.Response:
        self._rate_limit()
        logger.info("POST %s", url)
        resp = self.client.post(url, **kwargs)
        resp.raise_for_status()
        return resp
