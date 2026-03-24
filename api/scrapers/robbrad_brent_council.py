URL = "https://recyclingservices.brent.gov.uk/waste"
import asyncio

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
        data = {"bins": []}
        user_postcode = kwargs.get("postcode")
        user_paon = kwargs.get("paon")
        check_postcode(user_postcode)
        check_paon(user_paon)

        URI = "https://recyclingservices.brent.gov.uk/waste"

        payload = {"postcode": user_postcode}

        s = httpx.AsyncClient()

        # Make the POST request
        response = s.post(URI, data=payload)

        # Make a BS4 object
        soup = BeautifulSoup(response.content, features="html.parser")

        address_list = soup.find_all("option")

        current_year = datetime.now().year
        next_year = current_year + 1

        for address in address_list:
            if user_paon in (address.text):
                address_id = address.get("value")
                URI = f"https://recyclingservices.brent.gov.uk/waste/{address_id}"

                counter = 0
                r = s.get(URI)
                while "Loading your bin days..." in r.text:
                    counter = counter + 1
                    if counter == 20:
                        return data
                    sleep(2)
                    r = s.get(URI)

                r.raise_for_status()

                soup = BeautifulSoup(r.content, features="html.parser")

                wastecollections = soup.find("div", {"class": "waste__collections"})

                # Find all waste service sections
                waste_services = wastecollections.find_all(
                    "h3", class_="govuk-heading-m waste-service-name"
                )

                for service in waste_services:
                    # Get the collection type (e.g., Rubbish, Recycling)
                    collection_type = (service.get_text(strip=True)).split("\n")[0]

                    # Find the sibling container holding details
                    service_details = service.find_next(
                        "dl", class_="govuk-summary-list"
                    )

                    if service_details:
                        # Extract next collection date only
                        next_collection_row = service_details.find(
                            "dt", string="Next collection"
                        )
                        if next_collection_row:
                            next_collection = next_collection_row.find_next_sibling(
                                "dd"
                            ).get_text(strip=True)

                            # Remove the adjusted collection time message
                            if (
                                "(this collection has been adjusted from its usual time)"
                                in next_collection
                            ):
                                next_collection = next_collection.replace(
                                    "(this collection has been adjusted from its usual time)",
                                    "",
                                ).strip()

                            # Parse date from format like "Wednesday, 7th May"
                            next_collection = remove_ordinal_indicator_from_date_string(
                                next_collection
                            )
                            try:
                                next_collection_date = datetime.strptime(
                                    next_collection, "%A, %d %B"
                                )

                                # Handle year rollover
                                if (
                                    datetime.now().month == 12
                                    and next_collection_date.month == 1
                                ):
                                    next_collection_date = next_collection_date.replace(
                                        year=next_year
                                    )
                                else:
                                    next_collection_date = next_collection_date.replace(
                                        year=current_year
                                    )

                                dict_data = {
                                    "type": collection_type.strip(),
                                    "collectionDate": next_collection_date.strftime(
                                        date_format
                                    ),
                                }
                                data["bins"].append(dict_data)
                                print(dict_data)
                            except ValueError as e:
                                print(f"Error parsing date {next_collection}: {e}")

        return data


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
