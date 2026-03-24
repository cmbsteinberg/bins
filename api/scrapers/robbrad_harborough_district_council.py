URL = "https://www.harborough.gov.uk"
import httpx
import urllib3
from bs4 import BeautifulSoup

from uk_bin_collection.uk_bin_collection.common import *
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass

# Suppress SSL warnings when using verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# import the wonderful Beautiful Soup and the URL grabber
class CouncilClass(AbstractGetBinDataClass):
    """
    Concrete classes have to implement all abstract operations of the
    base class. They can also override some operations with a default
    implementation.
    """

    def parse_data(self, page: str, **kwargs) -> dict:

        user_uprn = kwargs.get("uprn")
        check_uprn(user_uprn)
        bindata = {"bins": []}

        URI1 = "https://harborough.fccenvironment.co.uk/"
        URI2 = "https://harborough.fccenvironment.co.uk/detail-address"

        # Make the GET request
        session = httpx.AsyncClient(follow_redirects=True)
        response = session.get(
            URI1
        )  # Initialize session state (cookies) required by URI2
        response.raise_for_status()  # Validate session initialization

        params = {"Uprn": user_uprn}
        response = session.post(URI2, data=params)

        # Check for service errors
        if response.status_code == 502:
            raise ValueError(
                f"The FCC Environment service is currently unavailable (502 Bad Gateway). "
                f"This is a temporary issue with the council's waste collection system. "
                f"Please try again later."
            )

        response.raise_for_status()

        soup = BeautifulSoup(response.content, features="html.parser")
        bin_collection = soup.find(
            "div", {"class": "blocks block-your-next-scheduled-bin-collection-days"}
        )

        if bin_collection is None:
            raise ValueError(
                f"Could not find bin collection data for UPRN {user_uprn}. "
                "The council website may have changed or the UPRN may be invalid."
            )

        lis = bin_collection.find_all("li")
        for li in lis:
            try:
                # Try the new format first (with span.pull-right)
                date_span = li.find("span", {"class": "pull-right"})
                if date_span:
                    date_text = date_span.text.strip()
                    date = datetime.strptime(date_text, "%d %B %Y").strftime("%d/%m/%Y")
                    # Extract bin type from the text before the span
                    bin_type = li.text.replace(date_text, "").strip()
                else:
                    # Fall back to old format (regex match)
                    split = re.match(r"(.+)\s(\d{1,2} \w+ \d{4})$", li.text)
                    if not split:
                        continue
                    bin_type = split.group(1).strip()
                    date = datetime.strptime(
                        split.group(2),
                        "%d %B %Y",
                    ).strftime("%d/%m/%Y")

                dict_data = {
                    "type": bin_type,
                    "collectionDate": date,
                }
                bindata["bins"].append(dict_data)
            except Exception:
                continue

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
