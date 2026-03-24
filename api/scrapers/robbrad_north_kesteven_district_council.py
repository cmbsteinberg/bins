URL = "https://www.n-kesteven.org.uk/bins/display?uprn=100030869513"
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

        data = {"bins": []}

        # Find the bin-dates div
        bin_dates_div = soup.find("div", {"class": "bin-dates"})
        if not bin_dates_div:
            return data

        # Find all list items with bin collection information
        for li in bin_dates_div.find_all("li", {"class": "text-large"}):
            # Extract bin type from the span tag
            bin_type_span = li.find("span", {"class": "font-weight-bold"})
            if not bin_type_span:
                continue
            
            bin_type = bin_type_span.get_text(strip=True)
            
            # Extract collection date from the strong tag
            date_strong = li.find("strong")
            if not date_strong:
                continue
            
            date_text = date_strong.get_text(strip=True)
            
            try:
                # Parse date in format "Monday, 2 February 2026"
                collection_date = datetime.strptime(date_text, "%A, %d %B %Y")
                
                # Get the full bin description (e.g., "Black (Residual waste)")
                # Extract text between bin type and " bin on"
                full_text = li.get_text(strip=True)
                # Pattern: "Black (Residual waste) bin on Monday, 2 February 2026"
                match = re.search(rf"{re.escape(bin_type)}\s+(.*?)\s+bin on", full_text)
                if match:
                    bin_description = match.group(1).strip()
                    if bin_description:
                        bin_type = f"{bin_type} {bin_description}"
                
                data["bins"].append(
                    {
                        "type": bin_type,
                        "collectionDate": collection_date.strftime(date_format),
                    }
                )
            except ValueError:
                # Skip if date parsing fails
                continue

        data["bins"].sort(
            key=lambda x: datetime.strptime(x.get("collectionDate"), date_format)
        )

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
