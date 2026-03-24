URL = "https://cms.northnorthants.gov.uk/bin-collection-search/calendarevents/100031021318/2023-10-17/2023-10-01"
import hashlib
import math
import time
from datetime import datetime as dtm, timedelta

from uk_bin_collection.uk_bin_collection.common import *
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass


def myFunc(e):
    return e["start"]


class CouncilClass(AbstractGetBinDataClass):
    """
    Concrete classes have to implement all abstract operations of the
    base class. They can also override some operations with a default
    implementation.
    """

    def parse_data(self, page: str, **kwargs) -> dict:
        data = {"bins": []}
        uprn = kwargs.get("uprn")
        check_uprn(uprn)
        today = int(datetime.now().timestamp()) * 1000
        dateforurl = datetime.now().strftime("%Y-%m-%d")
        dateforurl2 = (datetime.now() + timedelta(days=42)).strftime("%Y-%m-%d")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64)",
        }
        requests.packages.urllib3.disable_warnings()

        # Get variables for workings
        response = requests.get(
            f"https://cms.northnorthants.gov.uk/bin-collection-search/calendarevents/{uprn}/{dateforurl}/{dateforurl2}",
            headers=headers,
        )
        if response.status_code != 200:
            raise ValueError("No bin data found for provided UPRN..")

        json_response = json.loads(response.text)

        output_dict = [
            x
            for x in json_response
            if int("".join(filter(str.isdigit, x["start"]))) >= today
        ]

        output_json = output_dict
        output_json.sort(key=myFunc)

        i = 0
        while i < len(output_json):
            sov = output_json[i]["title"].lower()
            if "recycling" in sov:
                bin_type = "Recycling"
            elif "garden" in sov:
                bin_type = "Garden"
            elif "refuse" in sov:
                bin_type = "General"
            else:
                bin_type = "Unknown"
            dateofbin = int("".join(filter(str.isdigit, output_json[i]["start"])))
            day = dtm.fromtimestamp(dateofbin / 1000)
            collection_data = {
                "type": bin_type,
                "collectionDate": day.strftime(date_format),
            }
            data["bins"].append(collection_data)
            i += 1

        return data


# --- Adapter for Project API ---
from waste_collection_schedule import Collection

class Source:
    def __init__(self, uprn: str | None = None):
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
