URL = "https://calendar.google.com/calendar/ical/0d775884b4db6a7bae5204f06dae113c1a36e505b25991ebc27c6bd42edf5b5e%40group.calendar.google.com/public/basic.ics"
from datetime import datetime, timedelta
from typing import Any
import httpx
from icalevents.icalevents import events

from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass
from uk_bin_collection.uk_bin_collection.common import date_format


class CouncilClass(AbstractGetBinDataClass):
    def parse_data(self, page: str, **kwargs: Any) -> dict:
        ics_url: str = kwargs.get("url")

        if not ics_url:
            raise ValueError("Missing required argument: url")

        # Get events within the next 90 days
        now = datetime.now()
        future = now + timedelta(days=60)

        try:
            upcoming_events = events(ics_url, start=now, end=future)
        except Exception as e:
            raise ValueError(f"Error parsing ICS feed: {e}")

        bindata = {"bins": []}

        for event in sorted(upcoming_events, key=lambda e: e.start):
            if not event.summary or not event.start:
                continue

            bindata["bins"].append(
                {
                    "type": event.summary,
                    "collectionDate": event.start.date().strftime(date_format),
                }
            )

        return bindata


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
