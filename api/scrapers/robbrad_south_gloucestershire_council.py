URL = "https://api.southglos.gov.uk/wastecomp/GetCollectionDetails"
from datetime import timedelta

from uk_bin_collection.uk_bin_collection.common import *
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass


def format_bin_data(key: str, date: datetime):
    formatted_date = date.strftime(date_format)
    servicename = key.get("hso_servicename")
    print(servicename)
    if re.match(r"^Recycl", servicename) is not None:
        return [ ("Recycling", formatted_date) ]
    elif re.match(r"^Refuse", servicename) is not None:
        return [("General Waste (Black Bin)", formatted_date)]
    elif re.match(r"^Garden", servicename) is not None:
        return [("Garden Waste (Green Bin)", formatted_date)]
    elif re.match(r"^Food", servicename) is not None:
        return [("Food Waste", formatted_date)]
    else:
        return None


class CouncilClass(AbstractGetBinDataClass):
    def parse_data(self, page: str, **kwargs) -> dict:
        """
        Parse waste collection data for the given UPRN and return upcoming bin collections within the next eight weeks.
        
        Parameters:
            page (str): Raw page content (unused by this implementation; included for signature compatibility).
            uprn (str, keyword): Unique Property Reference Number used to query the South Gloucestershire collection API.
        
        Returns:
            dict: A mapping with a "bins" key containing a list of collection entries. Each entry is a dict with:
                - "type" (str): Human-friendly bin type (e.g., "Recycling", "General Waste (Black Bin)").
                - "collectionDate" (str): Formatted collection date string.
        
        Raises:
            ValueError: If the API returns no collection data for the provided UPRN.
        """
        uprn = kwargs.get("uprn")
        check_uprn(uprn)

        api_url = (
            f"https://api.southglos.gov.uk/wastecomp/GetCollectionDetails"
            f"?uprn={uprn}"
        )

        headers = {"content-type": "application/json"}

        response = requests.get(api_url, headers=headers)

        json_response = response.json()
        if not json_response:
            raise ValueError("No collection data found for provided UPRN.")

        collection_data = json_response.get('value')

        today = datetime.today()
        eight_weeks = datetime.today() + timedelta(days=8 * 7)
        data = {"bins": []}
        collection_tuple = []
        for collection in collection_data:
            print(collection)
            item = collection.get('hso_nextcollection')

            if not item:
                continue

            collection_date = datetime.fromisoformat(item)
            if today.date() <= collection_date.date() <= eight_weeks.date():
                bin_data = format_bin_data(collection, collection_date)
                if bin_data is not None:
                    for bin_date in bin_data:
                        collection_tuple.append(bin_date)

        ordered_data = sorted(collection_tuple, key=lambda x: x[1])

        for item in ordered_data:
            dict_data = {
                "type": item[0],
                "collectionDate": item[1],
            }
            data["bins"].append(dict_data)

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
