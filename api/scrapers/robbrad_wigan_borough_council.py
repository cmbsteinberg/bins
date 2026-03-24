URL = "https://apps.wigan.gov.uk/MyNeighbourhood/"
from datetime import datetime

import httpx
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
        # Get and check UPRN
        user_uprn = kwargs.get("uprn")
        check_uprn(user_uprn)
        user_uprn = user_uprn.zfill(
            12
        )  # Wigan is expecting 12 character UPRN or else it falls over, expects 0 padded UPRNS at the start for any that aren't 12 chars

        user_postcode = kwargs.get("postcode")
        check_postcode(user_postcode)

        # Start a new session to walk through the form
        requests.packages.urllib3.disable_warnings()
        s = httpx.AsyncClient()

        # Get our initial session running
        response = s.get("https://apps.wigan.gov.uk/MyNeighbourhood/")

        soup = BeautifulSoup(response.text, features="html.parser")
        soup.prettify()

        # Grab the ASP variables needed to continue
        payload = {
            "__VIEWSTATE": (soup.find("input", {"id": "__VIEWSTATE"}).get("value")),
            "__VIEWSTATEGENERATOR": (
                soup.find("input", {"id": "__VIEWSTATEGENERATOR"}).get("value")
            ),
            "__EVENTVALIDATION": (
                soup.find("input", {"id": "__EVENTVALIDATION"}).get("value")
            ),
            "ctl00$ContentPlaceHolder1$txtPostcode": (user_postcode),
            "ctl00$ContentPlaceHolder1$btnPostcodeSearch": ("Search"),
        }

        # Use the above to get to the next page with address selection
        response = s.post("https://apps.wigan.gov.uk/MyNeighbourhood/", data=payload)

        soup = BeautifulSoup(response.text, features="html.parser")
        soup.prettify()

        # Load the new variables that are constant and can't be gotten from the page
        payload = {
            "__EVENTTARGET": ("ctl00$ContentPlaceHolder1$lstAddresses"),
            "__EVENTARGUMENT": (""),
            "__LASTFOCUS": (""),
            "__VIEWSTATE": (soup.find("input", {"id": "__VIEWSTATE"}).get("value")),
            "__VIEWSTATEGENERATOR": (
                soup.find("input", {"id": "__VIEWSTATEGENERATOR"}).get("value")
            ),
            "__EVENTVALIDATION": (
                soup.find("input", {"id": "__EVENTVALIDATION"}).get("value")
            ),
            "ctl00$ContentPlaceHolder1$txtPostcode": (user_postcode),
            "ctl00$ContentPlaceHolder1$lstAddresses": ("UPRN" + user_uprn),
        }

        # Get the final page with the actual dates
        response = s.post("https://apps.wigan.gov.uk/MyNeighbourhood/", data=payload)

        soup = BeautifulSoup(response.text, features="html.parser")
        soup.prettify()

        data = {"bins": []}

        # Get the dates.
        for bins in soup.find_all("div", {"class": "BinsRecycling"}):
            bin_type = bins.find("h2").text
            binCollection = bins.find("div", {"class": "dateWrap-next"}).get_text(
                strip=True
            )
            binData = datetime.strptime(
                re.sub(r"(\d)(st|nd|rd|th)", r"\1", binCollection), "%A%d%b%Y"
            )
            if binData:
                dict_data = {
                    "type": bin_type,
                    "collectionDate": binData.strftime(date_format),
                }
                data["bins"].append(dict_data)

        return data


# --- Adapter for Project API ---
from waste_collection_schedule import Collection

class Source:
    def __init__(self, uprn: str | None = None, postcode: str | None = None):
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
