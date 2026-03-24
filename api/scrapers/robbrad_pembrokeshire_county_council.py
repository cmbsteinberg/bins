URL = "https://nearest.pembrokeshire.gov.uk/property/100100278790"
from datetime import datetime

import bs4.element
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
        # Make a BeautifulSoup object
        soup = BeautifulSoup(page.text, features="html.parser")

        data = {"bins": []}

        # Locate the section containing bin collection data
        bin_collection_divs = soup.find_all(
            "div", class_="col-6 col-md-4 text-center mb-3"
        )

        if not bin_collection_divs:
            raise ValueError("No bin collection data found in the provided HTML.")

        for bin_div in bin_collection_divs:
            # Get the image tag first to check if this is a bin collection div
            img_tag = bin_div.find("img")
            if (
                not img_tag
                or not img_tag.get("src")
                or "pembrokeshire.gov.uk/images" not in img_tag["src"]
            ):
                continue

            # Extract bin type - first try the image title
            bin_type = None
            if img_tag.get("title"):
                bin_type = img_tag["title"].strip()

            # If no title, get all text nodes and join them
            if not bin_type:
                # Get all text nodes that are not within a <strong> tag (to exclude the date)
                text_nodes = [
                    text.strip()
                    for text in bin_div.find_all(text=True, recursive=True)
                    if text.strip()
                    and not isinstance(text.parent, bs4.element.Tag)
                    or text.parent.name != "strong"
                ]
                if text_nodes:
                    bin_type = " ".join(text_nodes).strip()

            if not bin_type:
                continue  # Skip if we couldn't find a bin type

            # Extract collection date
            bin_date_tag = bin_div.find("strong")
            if not bin_date_tag:
                continue  # Skip if no date found

            bin_date = bin_date_tag.text.strip()

            try:
                # Parse the date into a datetime object
                collection_date = datetime.strptime(bin_date, "%d/%m/%Y")
                # Format date back to DD/MM/YYYY format as required by schema
                formatted_date = collection_date.strftime("%d/%m/%Y")
            except ValueError:
                continue  # Skip if date parsing fails

            # Append the bin data to the list
            dict_data = {
                "type": bin_type,
                "collectionDate": formatted_date,
            }
            data["bins"].append(dict_data)

        if not data["bins"]:
            raise ValueError(
                "No valid bin collection data could be parsed from the HTML."
            )

        # Sort the bins by collection date
        data["bins"].sort(
            key=lambda x: datetime.strptime(x["collectionDate"], "%d/%m/%Y")
        )

        print(data)

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
