URL = "https://wasteservice.lambeth.gov.uk/WhitespaceComms/GetServicesByUprn"
import httpx
from requests.structures import CaseInsensitiveDict

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
        Parse bin collection data for a given UPRN from the Lambeth waste service API.
        
        Posts the UPRN to the Lambeth "GetServicesByUprn" endpoint, extracts services that include a next collection date and a container, normalizes commercial container types to either "recycling" (if the container name contains "Recycling") or "refuse", and returns a dictionary with a "bins" list where each entry contains the bin type and the collection date formatted according to `date_format`.
        
        Parameters:
            page (str): HTML or page content provided to the parser (not used by this implementation).
            uprn (str, optional, in kwargs): The UPRN to query; required in kwargs as "uprn".
        
        Returns:
            dict: A dictionary with a single key "bins" mapping to a list of objects with:
                - "type" (str): Bin type (e.g., "recycling", "refuse", or the container's DisplayPhrase).
                - "collectionDate" (str): Collection date formatted using `date_format`.
        
        Raises:
            ConnectionRefusedError: If the API response status code is not 200.
        """
        user_uprn = kwargs.get("uprn")
        check_uprn(user_uprn)
        data = {"bins": []}

        url = "https://wasteservice.lambeth.gov.uk/WhitespaceComms/GetServicesByUprn"

        headers = CaseInsensitiveDict()
        headers["Content-Type"] = "application/json"

        body = {"uprn": user_uprn, "includeEventTypes": False, "includeFlags": True}
        json_data = json.dumps(body)

        res = requests.post(url, headers=headers, data=json_data)

        if res.status_code != 200:
            raise ConnectionRefusedError("Cannot connect to API!")

        json_data = res.json()

        if "SiteServices" in json_data:
            SiteServices = json_data["SiteServices"]
            for service in SiteServices:
                if "NextCollectionDate" in service:
                    NextCollectionDate = service["NextCollectionDate"]
                    if NextCollectionDate:
                        Container = service["Container"]
                        if Container:
                            if Container["DisplayPhrase"] == "commercial bin":
                                Bin_Type = (
                                    "recycling"
                                    if "Recycling" in Container["Name"]
                                    else "refuse"
                                )
                            else:
                                Bin_Type = Container["DisplayPhrase"]
                            dict_data = {
                                "type": Bin_Type,
                                "collectionDate": datetime.strptime(
                                    NextCollectionDate, "%d/%m/%Y"
                                ).strftime(date_format),
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
