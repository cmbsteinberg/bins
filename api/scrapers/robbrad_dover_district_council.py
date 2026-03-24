URL = "https://collections.dover.gov.uk/property"
import re
from datetime import datetime

from bs4 import BeautifulSoup

from uk_bin_collection.uk_bin_collection.common import *  # Consider specific imports
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass


class CouncilClass(AbstractGetBinDataClass):
    def parse_data(self, page: str, **kwargs) -> dict:

        try:
            user_uprn = kwargs.get("uprn")
            check_uprn(user_uprn)
            url = f"https://collections.dover.gov.uk/property/{user_uprn}"
            if not user_uprn:
                # This is a fallback for if the user stored a URL in old system. Ensures backwards compatibility.
                url = kwargs.get("url")
        except Exception as e:
            raise ValueError(f"Error getting identifier: {str(e)}")

        # Make a BS4 object
        page = requests.get(url)
        soup = BeautifulSoup(page.text, "html.parser")

        bins_data = {"bins": []}
        bin_collections = []

        results_wrapper = soup.find("div", {"class": "results-table-wrapper"})
        if not results_wrapper:
            return bins_data  # Return empty if the results wrapper is not found

        bins = results_wrapper.find_all("div", {"class": "service-wrapper"})
        for bin_item in bins:
            service_name = bin_item.find("h3", {"class": "service-name"})
            next_service = bin_item.find("td", {"class": "next-service"})

            if service_name and next_service:
                bin_type = service_name.get_text().replace("Collection", "bin").strip()
                date_span = next_service.find("span", {"class": "table-label"})
                date_text = (
                    date_span.next_sibling.get_text().strip() if date_span else None
                )

                if date_text and re.match(r"\d{2}/\d{2}/\d{4}", date_text):
                    try:
                        bin_date = datetime.strptime(date_text, "%d/%m/%Y")
                        bin_collections.append((bin_type, bin_date))
                    except ValueError:
                        continue

        for bin_type, bin_date in sorted(bin_collections, key=lambda x: x[1]):
            bins_data["bins"].append(
                {
                    "type": bin_type.capitalize(),
                    "collectionDate": bin_date.strftime("%d/%m/%Y"),
                }
            )

        return bins_data


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
