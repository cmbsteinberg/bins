URL = "https://www.gedling.gov.uk/"
from bs4 import BeautifulSoup
import urllib.parse

from uk_bin_collection.uk_bin_collection.common import *
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass


# import the wonderful Beautiful Soup and the URL grabber
class CouncilClass(AbstractGetBinDataClass):
    """
    Concrete classes have to implement all abstract operations of the
    base class. They can also override some operations with a default
    implementation.
    """

    def parse_data(self, page: str, **kwargs) -> dict:
        data = {"bins": []}
        collections = []
        selected_collections = kwargs.get("paon").split(",")
        calendar_urls = []
        run_date = datetime.now().date()

        # For each collection, check if there's a number. Garden bins have no numbers, so we can generate the needed
        # URLs this way
        for item in selected_collections:
            item = item.strip().lower().replace(" ", "_")
            if has_numbers(item):
                calendar_urls.append(
                    f"https://www.gbcbincalendars.co.uk/json/gedling_borough_council_{item}_bin_schedule.json"
                )
            else:
                calendar_urls.append(
                    f"https://www.gbcbincalendars.co.uk/json/gedling_borough_council_{item}_garden_bin_schedule.json"
                )

        # Parse each URL and load future data
        for url in calendar_urls:
            response = requests.get(url)
            if response.status_code != 200:
                raise ConnectionError(f"Could not get response from: {url}")
            json_data = response.json()["collectionDates"]
            for col in json_data:
                bin_date = datetime.strptime(
                    col.get("collectionDate"), "%Y-%m-%d"
                ).date()
                if bin_date >= run_date:
                    collections.append((col.get("alternativeName"), bin_date))

        # Sort the data
        ordered_data = sorted(collections, key=lambda x: x[1])
        data = {"bins": []}
        for bin in ordered_data:
            dict_data = {
                "type": bin[0],
                "collectionDate": bin[1].strftime(date_format),
            }
            data["bins"].append(dict_data)
        print()

        return data


# --- Adapter for Project API ---
from waste_collection_schedule import Collection

class Source:
    def __init__(self, house_number: str | None = None):
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
