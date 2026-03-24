URL = "https://www.gosport.gov.uk/refuserecyclingdays"
import httpx
from datetime import datetime
from uk_bin_collection.uk_bin_collection.common import date_format
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass


class CouncilClass(AbstractGetBinDataClass):
    """
    Concrete class for Gosport Borough Council bin collection data.
    Uses the Supatrak API to fetch collection schedules by postcode.
    """

    def parse_data(self, page: str, **kwargs) -> dict:
        """
        Fetch bin collection data for Gosport Borough Council using postcode.

        Args:
            page (str): Unused parameter (kept for interface compatibility).
            postcode (str, in kwargs): Postcode to search for collection data.

        Returns:
            dict: Dictionary containing bin collection data with structure:
                {
                    "bins": [
                        {
                            "type": str,  # Bin type (e.g., "DOMESTIC", "RECYCLING", "GARDEN")
                            "collectionDate": str  # Date in standard format
                        },
                        ...
                    ]
                }

        Raises:
            ValueError: If postcode is not provided or API request fails.
        """
        postcode = kwargs.get("postcode")
        if not postcode:
            raise ValueError("Postcode is required for Gosport Borough Council")

        # API endpoint from the council's website JavaScript
        api_url = "https://api.supatrak.com/API/JobTrak/NextCollection"
        
        # Headers from the council's website
        headers = {
            "Authorization": "Basic VTAwMDE4XEFQSTpUcjRja2luZzEh",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        params = {"postcode": postcode}

        try:
            response = requests.get(api_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to fetch bin collection data: {e}")

        if not data or len(data) == 0:
            raise ValueError(f"No collection data found for postcode: {postcode}")

        bins = []
        seen = set()  # Track unique type+date combinations
        
        for collection in data:
            waste_type = collection.get("WasteType", "Unknown")
            next_collection = collection.get("NextCollection")
            
            if next_collection:
                # Parse the date string (format: "2025-02-05T00:00:00")
                collection_date = datetime.fromisoformat(next_collection.replace("Z", "+00:00"))
                formatted_date = collection_date.strftime(date_format)
                
                # Create unique key to avoid duplicates
                unique_key = (waste_type, formatted_date)
                if unique_key not in seen:
                    seen.add(unique_key)
                    bins.append({
                        "type": waste_type,
                        "collectionDate": formatted_date
                    })

        return {"bins": bins}


# --- Adapter for Project API ---
from waste_collection_schedule import Collection

class Source:
    def __init__(self, postcode: str | None = None):
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
