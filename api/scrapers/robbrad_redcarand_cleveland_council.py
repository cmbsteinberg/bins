URL = "https://www.redcar-cleveland.gov.uk"
import time

import httpx

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

        user_postcode = kwargs.get("postcode")
        user_paon = kwargs.get("paon")
        check_postcode(user_postcode)
        check_paon(user_paon)
        bindata = {"bins": []}

        URI = "https://api.eu.recollect.net/api/areas/RedcarandClevelandUK/services/50006/address-suggest"

        params = {
            "q": user_postcode,
            "locale": "en-GB",
            "_": str(int(time.time() * 1000)),
        }

        # print(params)

        # Send GET request
        response = requests.get(URI, params=params)

        addresses = response.json()

        place_id = next(
            (
                item["place_id"]
                for item in addresses
                if item.get("name", "").startswith(user_paon)
            ),
            addresses[1]["place_id"] if addresses[1] else None,
        )

        # print(addresses)
        # print(f"PlaceID - {place_id}")

        URI = (
            f"https://api.eu.recollect.net/api/places/{place_id}/services/50006/events"
        )

        after = datetime.today()
        before = after + timedelta(days=30)

        after = after.strftime("%Y-%m-%d")
        before = before.strftime("%Y-%m-%d")

        # print(after)
        # print(before)

        params = {
            "nomerge": 1,
            "hide": "reminder_only",
            "after": after,
            "before": before,
            "locale": "en-GB",
            "include_message": "email",
            "_": str(int(time.time() * 1000)),
        }

        # print(params)

        # Send GET request
        response = requests.get(URI, params=params)

        response = response.json()

        bin_collection = response["events"]

        # print(bin_collection)

        # Extract "end_day" and "name"
        events = [
            (event["end_day"], flag["name"])
            for event in bin_collection
            for flag in event.get("flags", [])
        ]

        # Print results
        for end_day, bin_type in events:

            date = datetime.strptime(end_day, "%Y-%m-%d")

            dict_data = {
                "type": bin_type,
                "collectionDate": date.strftime(date_format),
            }
            bindata["bins"].append(dict_data)

        bindata["bins"].sort(
            key=lambda x: datetime.strptime(x.get("collectionDate"), date_format)
        )

        return bindata


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
