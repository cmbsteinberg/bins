URL = "https://www.northyorks.gov.uk/bin-calendar/lookup"
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from uk_bin_collection.uk_bin_collection.common import *
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass


class CouncilClass(AbstractGetBinDataClass):
    def parse_data(self, page: str, **kwargs) -> dict:
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
        response = requests.request("POST", url, headers=headers, data=payload)
        bin_data_url = f"{str(response.url)}/ajax"

        # Get bin data
        response = requests.request("GET", bin_data_url)
        bin_data = response.json()

        # Parse bin data
        soup = BeautifulSoup(bin_data[1]["data"], "html.parser")

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
            bin_types = [txt for txt in cols[2].stripped_strings]

            for sub_bin in bin_types:
                data["bins"].append(
                    {
                        "type": sub_bin,
                        "collectionDate": bin_date.strftime(date_format),
                    }
                )

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
