URL = "https://www.rochford.gov.uk/online-bin-collections-calendar"
from bs4 import BeautifulSoup
from uk_bin_collection.uk_bin_collection.common import *
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass
from dateutil.relativedelta import relativedelta
from datetime import timedelta


# import the wonderful Beautiful Soup and the URL grabber
class CouncilClass(AbstractGetBinDataClass):
    """
    Concrete classes have to implement all abstract operations of the
    base class. They can also override some operations with a default
    implementation.
    """

    def parse_data(self, page: str, **kwargs) -> dict:
        data = {"bins": []}

        # response = requests.get('https://www.rochford.gov.uk/online-bin-collections-calendar', headers=headers)
        soup = BeautifulSoup(page.text, features="html.parser")
        soup.prettify()
        year = soup.find_all("table", {"class": "responsive-enabled govuk-table"})

        current_month = datetime.now().strftime("%B %Y")
        next_month = (datetime.now() + relativedelta(months=1, day=1)).strftime("%B %Y")

        for month in year:
            heading = (
                month.find("th", {"class": "govuk-table__header"}).get_text().strip()
            )
            if heading == current_month or heading == next_month:
                for week in month.find("tbody").find_all(
                    "tr", {"class": "govuk-table__row"}
                ):
                    week_text = week.get_text().strip().split("\n")
                    date_str = week_text[0].split(" - ")[0].split("–")[0].strip()
                    collection_date = datetime.strptime(
                        remove_ordinal_indicator_from_date_string(date_str),
                        "%A %d %B",
                    )
                    next_collection = collection_date.replace(year=datetime.now().year)
                    if datetime.now().month == 12 and next_collection.month == 1:
                        next_collection = next_collection + relativedelta(years=1)
                    bin_type = (
                        week_text[1]
                        .replace("collection week", "bin")
                        .strip()
                        .capitalize()
                    )
                    if next_collection.date() >= (datetime.now().date() - timedelta(6)):
                        dict_data = {
                            "type": bin_type,
                            "collectionDate": next_collection.strftime(date_format),
                        }
                        data["bins"].append(dict_data)
            else:
                continue

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
