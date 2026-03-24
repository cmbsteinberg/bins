URL = "https://services.southwark.gov.uk/bins/lookup/"
from datetime import datetime

from bs4 import BeautifulSoup

from uk_bin_collection.uk_bin_collection.common import check_uprn
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass


def extract_collection_date(section, section_id):
    """
    Helper function to safely extract title and collection date from a section.
    Returns tuple (title, collection_date) or (None, None) if not found.
    """
    if not section:
        return None, None

    title_element = section.find("p", {"id": section_id})
    if not title_element:
        return None, None

    title = title_element.get_text(strip=True)

    next_collection_text = section.find(
        string=lambda t: isinstance(t, str) and "next collection" in t.lower()
    )

    if not next_collection_text:
        return title, None

    text = str(next_collection_text).strip()
    _, sep, rhs = text.partition(":")
    if not sep:
        return title, None
    collection_date = rhs.strip()
    return title, collection_date


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
        data = {"bins": []}

        baseurl = "https://services.southwark.gov.uk/bins/lookup/"
        url = baseurl + user_uprn

        # Make the web request using the common helper (standard UA, timeout, logging)
        response = self.get_data(url).text

        soup = BeautifulSoup(response, "html.parser")
        # Extract collection information for all bin types
        section_ids = (
            "recyclingCollectionTitle",
            "refuseCollectionTitle",
            "domesticFoodCollectionTitle",
            "communalFoodCollectionTitle",
            "recyclingCommunalCollectionTitle",
            "refuseCommunalCollectionTitle",
        )

        for section_id in section_ids:
            section = soup.find("div", {"aria-labelledby": section_id})
            if not section:
                continue

            title, next_collection = extract_collection_date(section, section_id)
            if not (title and next_collection):
                continue

            try:
                parsed = datetime.strptime(next_collection, "%a, %d %B %Y")
            except ValueError:
                continue

            data["bins"].append(
                {
                    "type": title,
                    "collectionDate": parsed.strftime("%d/%m/%Y"),
                }
            )

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
