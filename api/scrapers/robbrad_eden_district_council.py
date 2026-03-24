URL = "https://my.eden.gov.uk/myeden.aspx"
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

        user_uprn = kwargs.get("uprn")
        check_uprn(user_uprn)
        bindata = {"bins": []}

        URI = f"https://my.eden.gov.uk/myeden.aspx?action=SetAddress&UniqueId={user_uprn}"

        headers = {
            "user-agent": "Mozilla/5.0",
        }

        response = requests.get(URI, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        # Find the Refuse and Recycling panel by looking for the heading
        refuse_heading = soup.find("h3", {"id": "Refuse_and_Recycling"})
        
        if not refuse_heading:
            # Try alternative search
            refuse_heading = soup.find("h3", string=lambda text: text and "Refuse" in text)
        
        if not refuse_heading:
            return bindata

        # Find the parent panel and then the panel data
        refuse_panel = refuse_heading.find_parent("div", {"class": "atPanel"})
        
        if not refuse_panel:
            return bindata
            
        # Extract collection day information
        panel_data = refuse_panel.find("div", {"class": "atPanelData"})
        
        if not panel_data:
            return bindata

        # Parse the collection days text
        # The HTML uses <br> tags, so we need to parse differently
        # Format: "<strong> Blue refuse bags:</strong> Wednesday <br>"
        collection_info = {}
        
        # Get all the text and split by <br> tags
        html_content = str(panel_data)
        
        # Extract bin types and days using regex or simple parsing
        import re
        # Pattern: <strong>BIN_TYPE:</strong> DAY
        pattern = r'<strong>\s*([^:]+):</strong>\s*([^<\n]+)'
        matches = re.findall(pattern, html_content)
        
        for bin_type, day in matches:
            # Clean up whitespace in bin type and day names
            bin_type = ' '.join(bin_type.split())
            day = ' '.join(day.split())
            if day and day not in ['download', 'recycling calendar']:
                collection_info[bin_type] = day

        # Get current date and find next collection dates
        current_date = datetime.now()
        
        # Map day names to weekday numbers (Monday=0, Sunday=6)
        day_map = {
            "Monday": 0,
            "Tuesday": 1,
            "Wednesday": 2,
            "Thursday": 3,
            "Friday": 4,
            "Saturday": 5,
            "Sunday": 6
        }

        # Generate next 12 weeks of collections
        for bin_type, day_name in collection_info.items():
            if day_name in day_map:
                target_weekday = day_map[day_name]
                
                # Find next occurrence of this weekday
                days_ahead = target_weekday - current_date.weekday()
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                
                next_date = current_date + timedelta(days=days_ahead)
                
                # Add next 12 collections (weekly)
                for week in range(12):
                    collection_date = next_date + timedelta(weeks=week)
                    dict_data = {
                        "type": bin_type,
                        "collectionDate": collection_date.strftime(date_format),
                    }
                    bindata["bins"].append(dict_data)

        # Sort by date
        bindata["bins"].sort(
            key=lambda x: datetime.strptime(x.get("collectionDate"), date_format)
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
