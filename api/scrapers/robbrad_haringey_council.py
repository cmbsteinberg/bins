URL = "https://wastecollections.haringey.gov.uk/property"
from bs4 import BeautifulSoup
import httpx
import logging
import re
from typing import Dict, List, Any, Optional

from uk_bin_collection.uk_bin_collection.common import check_uprn
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass


class CouncilClass(AbstractGetBinDataClass):
    """
    Concrete classes have to implement all abstract operations of the
    base class. They can also override some operations with a default
    implementation.
    """

    def parse_data(self, page: str, **kwargs: Any) -> Dict[str, List[Dict[str, str]]]:
        data: Dict[str, List[Dict[str, str]]] = {"bins": []}

        uprn: Optional[str] = kwargs.get("uprn")

        if uprn is None:
            raise ValueError("UPRN is required and must be a non-empty string.")

        check_uprn(uprn)  # Assuming check_uprn() raises an exception if UPRN is invalid

        try:
            response = requests.post(
                f"https://wastecollections.haringey.gov.uk/property/{uprn}",
                timeout=10,  # Set a timeout for the request
            )
            response.raise_for_status()  # This will raise an exception for HTTP errors
        except httpx.HTTPError as e:
            logging.error(f"Network or HTTP error occurred: {e}")
            raise ConnectionError("Failed to retrieve data.") from e

        try:
            soup = BeautifulSoup(response.text, features="html.parser")
            soup.prettify()

            sections = soup.find_all("div", {"class": "property-service-wrapper"})

            date_regex = re.compile(r"\d{2}/\d{2}/\d{4}")
            for section in sections:
                service_name_element = section.find("h3", {"class": "service-name"})
                next_service_element = section.find("tbody").find(
                    "td", {"class": "next-service"}
                )

                if service_name_element and next_service_element:
                    service = service_name_element.text
                    next_collection = next_service_element.find(string=date_regex)

                    if next_collection:
                        dict_data = {
                            "type": service.replace("Collect ", "")
                            .replace("Paid ", "")
                            .strip(),
                            "collectionDate": next_collection.strip(),
                        }
                        data["bins"].append(dict_data)
        except Exception as e:
            logging.error(f"Error parsing data: {e}")
            raise ValueError("Error processing the HTML data.") from e

        return data


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
