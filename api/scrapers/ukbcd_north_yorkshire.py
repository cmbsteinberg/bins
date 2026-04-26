from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from api.compat.ukbcd.common import *
from api.compat.ukbcd.get_bin_data import AbstractGetBinDataClass
from api.compat import httpx_helpers as _http


class CouncilClass(AbstractGetBinDataClass):
    async def parse_data(self, page: str, **kwargs) -> dict:
        uprn = kwargs.get("uprn")
        check_uprn(uprn)

        # Figure bin data URL from UPRN
        url = "https://www.northyorks.gov.uk/bin-calendar/lookup"
        payload = {
            "selected_address": uprn,
            "submit": "Continue",
            "form_id": "bin_calendar_lookup_form",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        # This endpoint redirects to the data url.
        response = await _http.request("POST", url, headers=headers, data=payload)
        bin_data_url = f"{response.url}/ajax"

        # Get bin data
        response = await _http.request("GET", bin_data_url)
        bin_data = response.json()

        # Parse bin data
        html = next(
            cmd["data"]
            for cmd in bin_data
            if isinstance(cmd, dict) and isinstance(cmd.get("data"), str)
        )
        soup = BeautifulSoup(html, "html.parser")

        # All collection info is in the table
        table = (
            soup.find("div", {"id": "upcoming-collection"}).find("table").find("tbody")
        )
        rows = table.find_all("tr")

        data = {"bins": []}

        for row in rows:
            cols = row.find_all("td")
            # First column is date
            bin_date = datetime.strptime(cols[0].text.strip(), "%d %B %Y")

            # Third column may contain multiple bin types separated by line breaks
            # .stripped_strings yields a generator over all non-whitespace text segments
            bin_types = [
                br.next_sibling.strip()
                for br in cols[2].find_all("i")
                if br.next_sibling and isinstance(br.next_sibling, str) and br.next_sibling.strip()
            ]

            for sub_bin in bin_types:
                data["bins"].append(
                    {
                        "type": sub_bin,
                        "collectionDate": bin_date.strftime(date_format),
                    }
                )

        return data


# --- Adapter for Project API ---
from api.compat.hacs import Collection  # type: ignore[attr-defined]

TITLE = "North Yorkshire"
URL = "https://www.northyorks.gov.uk/bin-calendar/lookup"
TEST_CASES = {}


class Source:
    def __init__(self, uprn: str | None = None):
        self.uprn = uprn
        self._scraper = CouncilClass()

    async def fetch(self) -> list[Collection]:
        from datetime import datetime

        kwargs = {}
        if self.uprn: kwargs['uprn'] = self.uprn

        data = await self._scraper.parse_data("", **kwargs)

        entries = []
        if isinstance(data, dict) and "bins" in data:
            for item in data["bins"]:
                bin_type = item.get("type")
                date_str = item.get("collectionDate")
                if not bin_type or not date_str:
                    continue
                try:
                    if "-" in date_str:
                        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
                    elif "/" in date_str:
                        dt = datetime.strptime(date_str, "%d/%m/%Y").date()
                    else:
                        continue
                    entries.append(Collection(date=dt, t=bin_type, icon=None))
                except ValueError:
                    continue
        return entries
