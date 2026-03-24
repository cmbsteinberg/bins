URL = "https://bnr-wrp.whitespacews.com"
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

        """
        Parse scheduled bin collections for a given address and return structured bin data.
        
        Parameters:
            page (str): Unused; retained for interface compatibility.
            **kwargs: Keyword arguments containing address details:
                postcode (str): Postal code of the property.
                paon (str): Primary addressable object name/number (house number or name).
        
        Returns:
            dict: A dictionary with a "bins" key mapping to a list of collection records. Each record is a dict with:
                - "type" (str): The bin type/name.
                - "collectionDate" (str): The collection date formatted according to the module's date_format constant.
        
        Raises:
            Exception: If the initial landing page, address selection, or scheduled-collections section cannot be found, or if no scheduled services exist for the address.
        """
        user_postcode = kwargs.get("postcode")
        user_paon = kwargs.get("paon")
        check_postcode(user_postcode)
        check_paon(user_paon)
        bindata = {"bins": []}

        URI = "https://bnr-wrp.whitespacews.com/"

        session = httpx.AsyncClient()

        # get link from first page as has some kind of unique hash
        r = session.get(
            URI,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, features="html.parser")

        alink = soup.find("a", text="View my collections")

        if alink is None:
            raise Exception("Initial page did not load correctly")

        # greplace 'seq' query string to skip next step
        nextpageurl = alink["href"].replace("seq=1", "seq=2")

        data = {
            "address_name_number": user_paon,
            "address_postcode": user_postcode,
        }

        # get list of addresses
        r = session.post(nextpageurl, data=data)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, features="html.parser")

        # get first address (if you don't enter enough argument values this won't find the right address)
        alink = soup.find("div", id="property_list").find("a")

        if alink is None:
            raise Exception("Address not found")

        nextpageurl = URI + alink["href"]

        # get collection page
        r = session.get(
            nextpageurl,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, features="html.parser")

        if soup.find("span", id="waste-hint"):
            raise Exception("No scheduled services at this address")

        uls = soup.find("section", id="scheduled-collections").find_all("ul")

        for ul in uls:
            lis = ul.find_all("li", recursive=False)

            # Skip if not enough list items
            if len(lis) < 3:
                continue

            date = lis[1].text.replace("\n", "").strip()
            bin_type = lis[2].text.replace("\n", "").strip()

            dict_data = {
                "type": bin_type,
                "collectionDate": datetime.strptime(
                    date,
                    "%d/%m/%Y",
                ).strftime(date_format),
            }
            bindata["bins"].append(dict_data)

        bindata["bins"].sort(
            key=lambda x: datetime.strptime(x.get("collectionDate"), date_format)
        )

        return bindata

# --- Adapter for Project API ---
from waste_collection_schedule import Collection

class Source:
    def __init__(self, postcode: str | None = None, house_number: str | None = None):
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
