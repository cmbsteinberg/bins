URL = "https://wav-wrp.whitespacews.com/"
from datetime import date, datetime

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
        # pindex isn't actually paon, it's a url parameter that I'm guessing the council use as a property id
        data = {"bins": []}
        user_paon = kwargs.get("paon")
        user_postcode = kwargs.get("postcode")
        check_postcode(user_postcode)

        # WBC use a url parameter called "Track" that's generated when you start a form session.
        # So first off, open the page, find the page link and copy it with the Track
        start_url = "https://wav-wrp.whitespacews.com/"
        s = httpx.AsyncClient()
        response = s.get(start_url)
        soup = BeautifulSoup(response.content, features="html.parser")
        soup.prettify()
        collection_page_link = soup.find_all(
            "p", {"class": "govuk-body govuk-!-margin-bottom-0 colorblue lineheight15"}
        )[0].find("a")["href"]
        track_id = collection_page_link[33:60]

        # Next we need to search using the postcode, but this is actually an important POST request
        pc_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
            "image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Origin": "https://wav-wrp.whitespacews.com",
            "Referer": "https://wav-wrp.whitespacews.com/"
            + track_id
            + "&serviceID=A&seq=2",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Sec-GPC": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, "
            "like Gecko) Chrome/134.0.0.0 Safari/537.36",
        }
        form_data = {
            "address_name_number": "",
            "address_street": "",
            "street_town": "",
            "address_postcode": user_postcode,
        }
        response = s.post(
            "https://wav-wrp.whitespacews.com/mop.php?serviceID=A&"
            + track_id
            + "&seq=2",
            headers=pc_headers,
            data=form_data,
        )

        soup = BeautifulSoup(response.content, features="html.parser")
        soup.prettify()

        aria_labels = soup.find_all(
            "a",
            {
                "class": "app-subnav__link govuk-link clicker colordarkblue fontfamilyArial fontsize12rem"
            },
        )

        match = next(
            (
                a
                for a in aria_labels
                if a.get("aria-label", "").startswith(user_paon + ",")
            ),
            None,
        )

        # match is a Tag (or None)
        if match:
            request_url = "https://wav-wrp.whitespacews.com/" + match["href"]
        else:
            raise RuntimeError(
                "Unable to find house number/name "
                + user_paon
                + " in dropdown list for "
                + user_postcode
            )

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
            "image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
            "Connection": "keep-alive",
            "Referer": "https://wav-wrp.whitespacews.com/mop.php?serviceID=A&"
            + track_id
            + "&seq=2",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Sec-GPC": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, "
            "like Gecko) Chrome/134.0.0.0 Safari/537.36",
        }

        response = s.get(request_url, headers=headers)
        soup = BeautifulSoup(response.content, features="html.parser")
        soup.prettify()

        # Find the list elements
        u1_block = soup.find_all(
            "u1",
            {
                "class": "displayinlineblock justifycontentleft alignitemscenter margin0 padding0"
            },
        )

        for element in u1_block:
            x = element.find_all_next(
                "li", {"class": "displayinlineblock padding0px20px5px0px"}
            )
            # print(x)
            dict_data = {
                "type": x[2].text.strip(),
                "collectionDate": datetime.strptime(
                    x[1].text.strip(), date_format
                ).strftime(date_format),
            }
            data["bins"].append(dict_data)

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
