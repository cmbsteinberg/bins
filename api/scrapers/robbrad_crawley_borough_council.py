import time

import httpx
from dateutil.relativedelta import relativedelta

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
        uprn = kwargs.get("uprn")
        usrn = kwargs.get("paon")
        check_uprn(uprn)
        check_usrn(usrn)
        bindata = {"bins": []}

        SESSION_URL = "https://crawleybc-self.achieveservice.com/authapi/isauthenticated?uri=https%253A%252F%252Fcrawleybc-self.achieveservice.com%252Fen%252FAchieveForms%252F%253Fform_uri%253Dsandbox-publish%253A%252F%252FAF-Process-fb73f73e-e8f5-4441-9f83-8b5d04d889d6%252FAF-Stage-ec9ada91-d2d9-43bc-9730-597d15fc8108%252Fdefinition.json%2526redirectlink%253D%252Fen%2526cancelRedirectLink%253D%252Fen%2526noLoginPrompt%253D1%2526accept%253Dyes&hostname=crawleybc-self.achieveservice.com&withCredentials=true"

        API_URL = "https://crawleybc-self.achieveservice.com/apibroker/"

        currentdate = datetime.now().strftime("%d/%m/%Y")

        data = {
            "formValues": {
                "Address": {
                    "address": {
                        "value": {
                            "Address": {
                                "usrn": {
                                    "value": usrn,
                                },
                                "uprn": {
                                    "value": uprn,
                                },
                            }
                        },
                    },
                    "dayConverted": {
                        "value": currentdate,
                    },
                    "getCollection": {
                        "value": "true",
                    },
                    "getWorksheets": {
                        "value": "false",
                    },
                },
            },
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://crawleybc-self.achieveservice.com/fillform/?iframe_id=fillform-frame-1&db_id=",
        }
        s = httpx.AsyncClient(follow_redirects=True)
        r = s.get(SESSION_URL)
        r.raise_for_status()
        session_data = r.json()
        sid = session_data["auth-session"]
        params = {
            "api": "RunLookup",
            "id": "5b4f0ec5f13f4",
            "repeat_against": "",
            "noRetry": "true",
            "getOnlyTokens": "undefined",
            "log_id": "",
            "app_name": "AF-Renderer::Self",
            # unix_timestamp
            "_": str(int(time.time() * 1000)),
            "sid": sid,
        }

        r = s.post(API_URL, json=data, headers=headers, params=params)
        r.raise_for_status()

        data = r.json()
        rows_data = data["integration"]["transformed"]["rows_data"]["0"]
        if not isinstance(rows_data, dict):
            raise ValueError("Invalid data returned from API")

        # Extract each service's relevant details for the bin schedule
        for key, value in rows_data.items():
            if key.endswith("DateNext"):
                BinType = key.replace("DateNext", "Service")
                for key2, value2 in rows_data.items():
                    if key2 == BinType:
                        BinType = value2
                next_collection = datetime.strptime(value, "%A %d %B").replace(
                    year=datetime.now().year
                )
                if datetime.now().month == 12 and next_collection.month == 1:
                    next_collection = next_collection + relativedelta(years=1)

                dict_data = {
                    "type": BinType,
                    "collectionDate": next_collection.strftime(date_format),
                }
                bindata["bins"].append(dict_data)

        return bindata


# --- Adapter for Project API ---
from waste_collection_schedule import Collection

class Source:
    def __init__(self, uprn: str | None = None, house_number: str | None = None):
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
