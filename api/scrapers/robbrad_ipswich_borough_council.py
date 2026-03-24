URL = "https://app.ipswich.gov.uk/bin-collection/"
import re

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

    # Constants specific to IBC
    IBC_INCOMING_DATE_FORMAT = (
        r"\b(?:on\s+)?([A-Za-z]+ \d{1,2}(?:st|nd|rd|th)? [A-Za-z]+ \d{4})\b"
    )

    IBC_SUPPORTED_BINS_DICT = {
        "black": "General Waste",
        "blue": "Recycling Waste",
        "brown": "Garden Waste",
    }

    IBC_DIV_MARKER = "ibc-page-content-section"

    IBC_ENDPOINT = "https://app.ipswich.gov.uk/bin-collection/"

    def transform_date(self, date_str):
        date_str = re.sub(
            r"(\d{1,2})(st|nd|rd|th)", r"\1", date_str
        )  # Remove ordinal suffixes
        date_obj = datetime.strptime(date_str, "%A %d %B %Y")
        return date_obj.strftime(date_format)

    def parse_data(self, page: str, **kwargs) -> dict:

        user_paon = kwargs.get("paon")
        check_paon(user_paon)

        # Make the request
        form_data = {"street-input": user_paon}
        response = requests.post(self.IBC_ENDPOINT, data=form_data, timeout=10)
        soup = BeautifulSoup(response.content, features="html.parser")

        data = {"bins": []}

        # Start scarping
        div_section = soup.find("div", class_=self.IBC_DIV_MARKER)

        if div_section:
            li_elements = div_section.find_all(
                "li"
            )  # li element exists for each day a bin or bins will be collected.

            date_pattern = re.compile(self.IBC_INCOMING_DATE_FORMAT)

            for li in li_elements:
                distinct_collection_info = li.get_text()
                date_match = date_pattern.search(distinct_collection_info)

                if date_match:
                    date = date_match.group(1)

                    for supported_bin in self.IBC_SUPPORTED_BINS_DICT:
                        if supported_bin in distinct_collection_info:
                            # Transform the date from council format to expected UKBCD format
                            date_transformed = self.transform_date(date)

                            dict_data = {
                                "type": supported_bin.capitalize()
                                + " - "
                                + self.IBC_SUPPORTED_BINS_DICT[supported_bin],
                                "collectionDate": date_transformed,
                            }

                            data["bins"].append(dict_data)
        return data


# --- Adapter for Project API ---
from waste_collection_schedule import Collection

class Source:
    def __init__(self, house_number: str | None = None):
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
