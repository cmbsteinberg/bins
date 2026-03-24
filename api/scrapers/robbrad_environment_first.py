URL = "https://environmentfirst.co.uk/house.php?uprn=100060055444"
# Legacy script. Copied to Lewes and Eastbourne.

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

    def parse_data(self, page: str, **kwargs) -> dict:
        # Make a BS4 object
        soup = BeautifulSoup(page.text, features="html.parser")
        soup.prettify()

        # Get the paragraph lines from the page
        data = {"bins": []}
        page_text = soup.find("div", {"class": "collect"}).find_all("p")

        # Parse the correct lines (find them, remove the ordinal indicator and make them the correct format date) and
        # then add them to the dictionary
        rubbish_day = datetime.strptime(
            remove_ordinal_indicator_from_date_string(
                page_text[2].find_next("strong").text
            ),
            "%d %B %Y",
        ).strftime(date_format)
        dict_data = {
            "type": "Rubbish",
            "collectionDate": rubbish_day,
        }
        data["bins"].append(dict_data)
        recycling_day = datetime.strptime(
            remove_ordinal_indicator_from_date_string(
                page_text[4].find_next("strong").text
            ),
            "%d %B %Y",
        ).strftime(date_format)
        dict_data = {
            "type": "Recycling",
            "collectionDate": recycling_day,
        }
        data["bins"].append(dict_data)

        if len(page_text) > 5:
            garden_day = datetime.strptime(
                remove_ordinal_indicator_from_date_string(
                    page_text[6].find_next("strong").text
                ),
                "%d %B %Y",
            ).strftime(date_format)
            dict_data = {
                "type": "Garden",
                "collectionDate": garden_day,
            }
            data["bins"].append(dict_data)

        return data


# --- Adapter for Project API ---
from waste_collection_schedule import Collection

class Source:
    def __init__(self):
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
