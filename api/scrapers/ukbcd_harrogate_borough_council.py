from bs4 import BeautifulSoup
from api.compat.ukbcd.common import *
from api.compat.ukbcd.get_bin_data import AbstractGetBinDataClass
from api.compat import httpx_helpers as _http


# import the wonderful Beautiful Soup and the URL grabber
class CouncilClass(AbstractGetBinDataClass):
    """
    Concrete classes have to implement all abstract operations of the
    base class. They can also override some operations with a default
    implementation.
    """

    async def parse_data(self, page: str, **kwargs) -> dict:
        user_uprn = kwargs.get("uprn")
        check_uprn(user_uprn)

        data = {"bins": []}

        headers = {
            "accept-language": "en-GB,en;q=0.9",
            "cache-control": "no-cache",
        }

        req_data = {
            "uprn": user_uprn,
        }

        url = f"https://secure.harrogate.gov.uk/inmyarea/Property/?uprn={user_uprn}"

        pass  # urllib3 warnings disabled
        response = await _http.post(url, headers=headers)

        soup = BeautifulSoup(response.text, features="html.parser")
        soup.prettify()

        collections = []

        # Find section with bins in
        table = soup.find_all("table", {"class": "hbcRounds"})[-1]

        # For each bin section, get the text and the list elements
        for row in table.find_all("tr"):
            bin_type = row.find("th").text
            td = row.find("td")
            for span in td.find_all("span"):
                span.extract()
            collectionDate = td.text.strip()
            next_collection = datetime.strptime(collectionDate, "%a %d %b %Y")
            collections.append((bin_type, next_collection))

        # Sort the text and list elements by date
        ordered_data = sorted(collections, key=lambda x: x[1])

        # Put the elements into the dictionary
        for item in ordered_data:
            dict_data = {
                "type": item[0],
                "collectionDate": item[1].strftime(date_format),
            }
            data["bins"].append(dict_data)

        return data


# --- Adapter for Project API ---
from api.compat.hacs import Collection  # type: ignore[attr-defined]

TITLE = "Harrogate"
URL = "https://secure.harrogate.gov.uk/inmyarea"
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
