URL = "https://www.south-ayrshire.gov.uk/"
import json
from datetime import timedelta

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
        # Get and check both the passed UPRN and postcode
        user_uprn = kwargs.get("uprn")
        check_uprn(user_uprn)
        user_postcode = kwargs.get("postcode")
        check_postcode(user_postcode)

        # Build the headers, specify the parameters and then make a GET for the calendar
        headers = {
            "Connection": "Keep-Alive",
            "User-Agent": "okhttp/3.14.9",
        }
        params = {
            "end_date": "2024-01-01",
            "rn": user_uprn,
            "device": "undefined",
            "postcode": user_postcode,
            "OS": "android",
            "OS_ver": "31",
            "app_ver": "35",
        }
        requests.packages.urllib3.disable_warnings()
        response = requests.get(
            "http://www.sac-bins.co.uk/get_calendar.php", params=params, headers=headers
        )

        # Load the response as JSON
        json_data = json.loads(response.text)

        # The response loads well over a year's worth of data, so figure out some dates to limit output
        today = datetime.today()
        eight_weeks = datetime.today() + timedelta(days=8 * 7)
        data = {"bins": []}

        # The bin titles are pretty weird and colours are too basic, so make the names match the app
        bin_friendly_names = {
            "blue": "Blue Bin",
            "red": "Food Caddy",
            "green": "Green Bin",
            "grey": "Grey Bin",
            "purple": "Purple Bin",
            "brown": "Brown Bin",
        }

        # Loop through the results. When a date is found that's on or greater than today's date AND less than
        # eight weeks away, we want it in the output. So look up the friendly name and add it in.
        for item in json_data:
            bin_date = datetime.strptime(item["start"], "%Y-%m-%d").date()
            if today.date() <= bin_date <= eight_weeks.date():
                bin_type = bin_friendly_names.get(item["className"])
                dict_data = {
                    "type": bin_type,
                    "collectionDate": bin_date.strftime(date_format),
                }
                data["bins"].append(dict_data)

        return data


# --- Adapter for Project API ---
from waste_collection_schedule import Collection

class Source:
    def __init__(self, uprn: str | None = None, postcode: str | None = None):
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
