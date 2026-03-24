URL = "https://lisburn.isl-fusion.com"
import difflib
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup

from uk_bin_collection.uk_bin_collection.common import *
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass


# import the wonderful Beautiful Soup and the URL grabber
class CouncilClass(AbstractGetBinDataClass):
    """
    Concrete classes have to implement all abstract operations of the
    base class. They can also override some operations with a default
    implementation.
    """

    base_url = "https://lisburn.isl-fusion.com"

    def parse_data(self, page: str, **kwargs) -> dict:
        """
        This function will make a request to the search endpoint with the postcode, extract the
        house numbers from the responses, then retrieve the ID of the entry with the house number that matches,
        to then retrieve the bin schedule.

        The API here is a weird combination of HTML in json responses.
        """
        postcode = kwargs.get("postcode")
        paon = kwargs.get("paon")

        if not postcode:
            raise ValueError("Must provide a postcode")

        if not paon:
            raise ValueError("Must provide a house number")

        search_url = f"{self.base_url}/address/{postcode}"

        requests.packages.urllib3.disable_warnings()
        s = httpx.AsyncClient()
        response = s.get(search_url)
        response.raise_for_status()

        address_data = response.json()

        address_list = address_data["html"]

        soup = BeautifulSoup(address_list, features="html.parser")

        address_by_id = {}

        for li in soup.find_all("li"):
            link = li.find_all("a")[0]
            address_id = link.attrs["href"]
            address = link.text

            address_by_id[address_id] = address

        addresses = list(address_by_id.values())

        common = difflib.SequenceMatcher(
            a=addresses[0], b=addresses[1]
        ).find_longest_match()
        extra_bit = addresses[0][common.a : common.a + common.size]

        ids_by_paon = {
            a.replace(extra_bit, ""): a_id.replace("/view/", "").replace("/", "")
            for a_id, a in address_by_id.items()
        }

        property_id = ids_by_paon.get(paon)
        if not property_id:
            raise ValueError(
                f"Invalid house number, valid values are {', '.join(ids_by_paon.keys())}"
            )

        today = date.today()
        calendar_url = (
            f"{self.base_url}/calendar/{property_id}/{today.strftime('%Y-%m-%d')}"
        )
        response = s.get(calendar_url)
        response.raise_for_status()
        calendar_data = response.json()
        next_collections = calendar_data["nextCollections"]

        collections = list(next_collections["collections"].values())

        data = {"bins": []}

        for collection in collections:
            collection_date = datetime.strptime(collection["date"], "%Y-%m-%d")
            bins = [c["name"] for c in collection["collections"].values()]

            for bin in bins:
                data["bins"].append(
                    {
                        "type": bin,
                        "collectionDate": collection_date.strftime(date_format),
                    }
                )
        return data


# --- Adapter for Project API ---
from waste_collection_schedule import Collection

class Source:
    def __init__(self, postcode: str | None = None, house_number: str | None = None):
        self.uprn = uprn
        self.postcode = postcode
        self.house_number = house_number
        self.usrn = usrn
        self._scraper = CouncilClass()

    async def fetch(self) -> list[Collection]:
        import asyncio
        from datetime import datetime

        # Run the synchronous scraper in a thread
        # We wrap the call to get_data or whichever method is the entry point
        # Heuristic: Most RobBrad scrapers seem to use 'get_data' or 'get_date_data'
        # But we need to check the specific class. 
        # For this generic adapter, we assume 'get_data' or similar.
        
        # NOTE: This is a best-effort adapter. 
        # You may need to manually adjust the method call if it differs.
        
        try:
             # Prepare kwargs
            kwargs = {}
            if self.postcode: kwargs['postcode'] = self.postcode
            if self.uprn: kwargs['uprn'] = self.uprn
            if self.house_number: kwargs['house_number'] = self.house_number
            if self.usrn: kwargs['usrn'] = self.usrn
            
            # Helper to run sync method
            def _run_scraper():
                # Try common method names
                if hasattr(self._scraper, 'get_data'):
                    return self._scraper.get_data(**kwargs)
                if hasattr(self._scraper, 'get_date_data'):
                     return self._scraper.get_date_data(**kwargs)
                raise NotImplementedError("Could not find fetch method on scraper")

            data = await asyncio.to_thread(_run_scraper)
            
            # Parse result
            # Expected format: { "bins": [ { "type": "...", "collectionDate": "..." } ] }
            
            entries = []
            if isinstance(data, dict) and "bins" in data:
                for item in data["bins"]:
                    bin_type = item.get("type")
                    date_str = item.get("collectionDate")
                    
                    if not bin_type or not date_str:
                        continue
                        
                    # Parse date (RobBrad uses various formats, but often YYYY-MM-DD or DD/MM/YYYY)
                    # We might need a robust parser.
                    # For now, assume generic parsing or pass string if allowed (Collection expects date obj)
                    
                    try:
                        # naive attempt at ISO
                        if "-" in date_str:
                             dt = datetime.strptime(date_str, "%Y-%m-%d").date()
                        elif "/" in date_str:
                             dt = datetime.strptime(date_str, "%d/%m/%Y").date()
                        else:
                            continue # skip unparseable
                            
                        entries.append(Collection(date=dt, t=bin_type, icon=None))
                    except ValueError:
                        continue
                        
            return entries

        except Exception as e:
            # Log error
            print(f"Scraper failed: {e}")
            raise
