URL = "https://forms.chorleysouthribble.gov.uk/xfp/form/70"
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
import httpx
import re
from datetime import datetime
from uk_bin_collection.uk_bin_collection.common import check_uprn, check_postcode, date_format
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass
from dateutil.parser import parse


class CouncilClass(AbstractGetBinDataClass):
    def get_data(self, url: str) -> str:
        # This method is not used in the current implementation
        return ""

    def parse_data(self, page: str, **kwargs: Any) -> Dict[str, List[Dict[str, str]]]:
        postcode: Optional[str] = kwargs.get("postcode")
        uprn: Optional[str] = kwargs.get("uprn")

        if postcode is None or uprn is None:
            raise ValueError("Both postcode and UPRN are required.")

        check_postcode(postcode)
        check_uprn(uprn)

        session = httpx.AsyncClient()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
            )
        }
        session.headers.update(headers)

        # Step 1: Load form and get token + field names
        initial_url = "https://forms.chorleysouthribble.gov.uk/xfp/form/70"
        get_resp = session.get(initial_url)
        soup = BeautifulSoup(get_resp.text, "html.parser")

        token = soup.find("input", {"name": "__token"})["value"]
        page_id = soup.find("input", {"name": "page"})["value"]
        postcode_field = soup.find("input", {"type": "text", "name": re.compile(".*_0_0")})["name"]

        # Step 2: Submit postcode
        post_resp = session.post(
            initial_url,
            data={
                "__token": token,
                "page": page_id,
                "locale": "en_GB",
                postcode_field: postcode,
                "next": "Next",
            },
        )

        soup = BeautifulSoup(post_resp.text, "html.parser")
        token = soup.find("input", {"name": "__token"})["value"]
        address_field_el = soup.find("select", {"name": re.compile(".*_1_0")})
        if not address_field_el:
            raise ValueError("Failed to find address dropdown after postcode submission.")

        address_field = address_field_el["name"]

        # Step 3: Submit UPRN and retrieve bin data
        final_resp = session.post(
            initial_url,
            data={
                "__token": token,
                "page": page_id,
                "locale": "en_GB",
                postcode_field: postcode,
                address_field: uprn,
                "next": "Next",
            },
        )

        soup = BeautifulSoup(final_resp.text, "html.parser")
        table = soup.find("table", class_="data-table")
        if not table:
            raise ValueError("Could not find bin collection table.")

        rows = table.find("tbody").find_all("tr")
        data: Dict[str, List[Dict[str, str]]] = {"bins": []}

        # Extract bin type mapping from JavaScript
        bin_type_map = {}
        scripts = soup.find_all("script", type="text/javascript")
        for script in scripts:
            if script.string and "const bintype = {" in script.string:
                match = re.search(r'const bintype = \{([^}]+)\}', script.string, re.DOTALL)
                if match:
                    bintype_content = match.group(1)
                    for line in bintype_content.split('\n'):
                        line = line.strip()
                        if '"' in line and ':' in line:
                            parts = line.split(':', 1)
                            if len(parts) == 2:
                                key = parts[0].strip().strip('"').strip("'")
                                value = parts[1].strip().rstrip(',').strip().strip('"').strip("'")
                                bin_type_map[key] = value
                    break

        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                bin_type_cell = cells[0]
                bin_type = bin_type_cell.get_text(strip=True)
                bin_type = bin_type_map.get(bin_type, bin_type)

                date_text = cells[1].get_text(strip=True)
                date_parts = date_text.split(", ")
                date_str = date_parts[1] if len(date_parts) == 2 else date_text

                try:
                    day, month, year = date_str.split('/')
                    year = int(year)
                    if year < 100:
                        year = 2000 + year

                    date_obj = datetime(year, int(month), int(day)).date()

                    data["bins"].append({
                        "type": bin_type,
                        "collectionDate": date_obj.strftime(date_format)
                    })
                except Exception:
                    continue

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
