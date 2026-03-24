URL = "https://www.southlanarkshire.gov.uk/directory_record/579973/abbeyhill_crescent_lesmahagow"
import time
from datetime import timedelta

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
        """
        Parse an HTML page to extract scheduled bin collection types and their collection dates.

        Parameters:
            page: An object with a `text` attribute containing the HTML of the council's bin collection page (e.g., an HTTP response).

        Returns:
            dict: A dictionary with a "bins" key mapping to a list of collections, where each collection is a dict with:
                - "type": the collection description string (e.g., "Garden waste")
                - "collectionDate": the collection date formatted according to the module's `date_format`
        """
        data = {"bins": []}
        collection_types = [
            "non recyclable waste",
            "food and garden",
            "paper and card",
            "glass, cans and plastics",
        ]

        # Make a BS4 object
        soup = BeautifulSoup(page.text, features="html.parser")
        soup.prettify()

        week_details = soup.find("div", {"class": "bin-dir-snip"})
        week_dates = week_details.find("div", {"class": "clearfix"}).find("p")
        week_collections = week_details.find_all_next("h4")

        results = re.search(
            "([A-Za-z0-9 ]+) to ([A-Za-z0-9 ]+)", week_dates.get_text().strip()
        )
        if results:
            week_start = datetime.strptime(results.groups()[0], "%A %d %B %Y")
            week_end = datetime.strptime(results.groups()[1], "%A %d %B %Y")
            week_days = (
                week_start + timedelta(days=i)
                for i in range((week_end - week_start).days + 1)
            )

            week_collection_types = []
            for week_collection in week_collections:
                week_collection = (
                    week_collection.get_text().strip().lower().replace("-", " ")
                )
                for collection_type in collection_types:
                    if collection_type in week_collection:
                        week_collection_types.append(collection_type)

            collection_schedule = (
                soup.find("div", {"class": "serviceDetails"})
                .find("table")
                .find_all_next("tr")
            )
            for day in week_days:
                for row in collection_schedule:
                    schedule_type = row.find("th").get_text().strip()

                    # collection schedule contains area name -> filter out
                    if schedule_type == "Area":
                        continue

                    results2 = re.search("([^(]+)", row.find("td").get_text().strip())
                    schedule_cadence = row.find("td").get_text().strip().split(" ")[1]
                    if results2:
                        schedule_day = results2[1].strip()
                        for collection_type in week_collection_types:
                            collectionDate = None
                            if collection_type in schedule_type.lower():
                                if (
                                    day.weekday()
                                    == time.strptime(schedule_day, "%A").tm_wday
                                ):
                                    collectionDate = day.strftime(date_format)
                            else:
                                if "Fortnightly" in schedule_cadence:
                                    if (
                                        day.weekday()
                                        == time.strptime(schedule_day, "%A").tm_wday
                                    ):
                                        adjusted_day = day + timedelta(days=7)
                                        collectionDate = adjusted_day.strftime(
                                            date_format
                                        )

                            if schedule_type and collectionDate:
                                dict_data = {
                                    "type": schedule_type,
                                    "collectionDate": collectionDate,
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
