URL = "https://myproperty.molevalley.gov.uk/molevalley/"
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from uk_bin_collection.uk_bin_collection.common import *
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass


class CouncilClass(AbstractGetBinDataClass):
    def parse_data(self, page: str, **kwargs) -> dict:

        user_postcode = kwargs.get("postcode")
        check_postcode(user_postcode)

        # Fetch the page content
        root_url = "https://myproperty.molevalley.gov.uk/molevalley/api/live_addresses/{}?format=json".format(
            user_postcode
        )
        response = requests.get(root_url)

        if not response.ok:
            raise ValueError("Invalid server response code retrieving data.")

        jsonData = response.json()

        if len(jsonData["results"]["features"]) == 0:
            raise ValueError("No collection data found for postcode provided.")

        properties_found = jsonData["results"]["features"]

        html_data = None
        uprn = kwargs.get("uprn")
        if uprn:
            check_uprn(uprn)
            for item in properties_found:
                if uprn == str(int(item["properties"]["blpu_uprn"])):
                    html_data = item["properties"]["three_column_layout_html"]
                    break
            if html_data is None:
                raise ValueError("No collection data found for UPRN provided.")
        else:
            html_data = properties_found[0]["properties"]["three_column_layout_html"]

        # Conditionally replace the commented-out sections (<!-- ... -->)
        if "<!--" in html_data and "-->" in html_data:
            print("Commented-out section found, replacing comments...")
            html_data = html_data.replace("<!--", "").replace("-->", "")
        else:
            print("No commented-out section found, processing as is.")

        # Process the updated HTML data with BeautifulSoup
        soup = BeautifulSoup(html_data, "html.parser")

        data = {"bins": []}
        all_collection_dates = []
        regex_date = re.compile(r"(\d{2}/\d{2}/\d{4})")  # Adjusted date regex
        regex_additional_collection = re.compile(r"We also collect (.*) on (.*) -")

        # Debugging to verify the HTML content is parsed correctly
        print("HTML content parsed successfully.")

        # Search for the 'Bins and Recycling' panel
        bins_panel = soup.find("h2", string="Bins and Recycling")
        if bins_panel:
            panel = bins_panel.find_parent("div", class_="panel")
            print("Found 'Bins and Recycling' panel.")

            # Extract bin collection info from the un-commented HTML
            for strong_tag in panel.find_all("strong"):
                bin_type = strong_tag.text.strip()
                collection_string = strong_tag.find_next("p").text.strip()

                # Debugging output
                print(f"Processing bin type: {bin_type}")
                print(f"Collection string: {collection_string}")

                match = regex_date.search(collection_string)
                if match:
                    collection_date = datetime.strptime(
                        match.group(1), "%d/%m/%Y"
                    ).date()
                    data["bins"].append(
                        {
                            "type": bin_type,
                            "collectionDate": collection_date.strftime("%d/%m/%Y"),
                        }
                    )
                    all_collection_dates.append(collection_date)
                else:
                    # Add a debug line to show which collections are missing dates
                    print(f"No valid date found for bin type: {bin_type}")

            # Search for additional collections like electrical and textiles
            for p in panel.find_all("p"):
                additional_match = regex_additional_collection.match(p.text.strip())

                # Debugging output for additional collections
                if additional_match:
                    bin_type = additional_match.group(1)
                    print(f"Found additional collection: {bin_type}")
                    if "each collection day" in additional_match.group(2):
                        if all_collection_dates:
                            collection_date = min(all_collection_dates)
                            data["bins"].append(
                                {
                                    "type": bin_type,
                                    "collectionDate": collection_date.strftime(
                                        "%d/%m/%Y"
                                    ),
                                }
                            )
                        else:
                            print(
                                "No collection dates available for additional collection."
                            )
                            raise ValueError("No valid bin collection dates found.")
                else:
                    print(
                        f"No additional collection found in paragraph: {p.text.strip()}"
                    )
        else:
            raise ValueError(
                "Unable to find 'Bins and Recycling' panel in the HTML data."
            )

        # Debugging to check collected data
        print(f"Collected bin data: {data}")

        # Handle the case where no collection dates were found
        if not all_collection_dates:
            raise ValueError("No valid collection dates were found in the data.")

        return data


# --- Adapter for Project API ---
from waste_collection_schedule import Collection

class Source:
    def __init__(self, uprn: str | None = None, postcode: str | None = None):
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
