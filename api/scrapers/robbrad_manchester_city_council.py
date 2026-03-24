from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from uk_bin_collection.uk_bin_collection.common import *
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass


class CouncilClass(AbstractGetBinDataClass):
    """
    Concrete classes have to implement all abstract operations of the
    base class. They can also override some operations with a default
    implementation.
    """

    def parse_data(self, page: str, **kwargs) -> dict:
        # Get and check UPRN
        user_uprn = kwargs.get("uprn")
        check_uprn(user_uprn)
        bindata = {"bins": []}

        COLLECTION_MAP = {
            "ahtm_dates_black_bin": "Black bin",
            "ahtm_dates_brown_commingled_bin": "Brown bin",
            "ahtm_dates_blue_pulpable_bin": "Blue bin",
            "ahtm_dates_green_organic_bin": "Green Bin",
        }

        API_URL = "https://manchester.form.uk.empro.verintcloudservices.com/api/custom?action=bin_checker-get_bin_col_info&actionedby=_KDF_custom&loadform=true&access=citizen&locale=en"
        AUTH_URL = "https://manchester.form.uk.empro.verintcloudservices.com/api/citizen?archived=Y&preview=false&locale=en"
        AUTH_KEY = "Authorization"

        r = requests.get(AUTH_URL)
        r.raise_for_status()
        auth_token = r.headers[AUTH_KEY]

        post_data = {
            "name": "sr_bin_coll_day_checker",
            "data": {
                "uprn": user_uprn,
                "nextCollectionFromDate": (datetime.now() - timedelta(days=1)).strftime(
                    "%Y-%m-%d"
                ),
                "nextCollectionToDate": (datetime.now() + timedelta(days=30)).strftime(
                    "%Y-%m-%d"
                ),
            },
            "email": "",
            "caseid": "",
            "xref": "",
            "xref1": "",
            "xref2": "",
        }

        headers = {
            "referer": "https://manchester.portal.uk.empro.verintcloudservices.com/",
            "accept": "application/json",
            "content-type": "application/json",
            AUTH_KEY: auth_token,
        }

        r = requests.post(API_URL, data=json.dumps(post_data), headers=headers)
        r.raise_for_status()

        result = r.json()
        print(result["data"])

        for key, value in result["data"].items():
            if key.startswith("ahtm_dates_"):
                print(key)
                print(value)

                dates_list = [
                    datetime.strptime(date.strip(), "%d/%m/%Y %H:%M:%S").date()
                    for date in value.split(";")
                    if date.strip()
                ]

                for current_date in dates_list:
                    dict_data = {
                        "type": COLLECTION_MAP.get(key),
                        "collectionDate": current_date.strftime(date_format),
                    }
                    bindata["bins"].append(dict_data)

        bindata["bins"].sort(
            key=lambda x: datetime.strptime(x.get("collectionDate"), "%d/%m/%Y")
        )
        return bindata


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
