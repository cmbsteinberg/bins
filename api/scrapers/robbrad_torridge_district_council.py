URL = "https://collections-torridge.azurewebsites.net/WebService2.asmx"
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from uk_bin_collection.uk_bin_collection.common import *
from uk_bin_collection.uk_bin_collection.get_bin_data import AbstractGetBinDataClass


# import the wonderful Beautiful Soup and the URL grabber
class CouncilClass(AbstractGetBinDataClass):
    """
    Concrete classes have to implement all abstract operations of the
    baseclass. They can also override some
    operations with a default implementation.
    """

    def parse_data(self, page, **kwargs) -> dict:
        """This method makes the request to the council

        Keyword arguments:
        url -- the url to get the data from
        """
        # Set a user agent so we look like a browser ;-)
        user_agent = "Mozilla/5.0 (Windows NT 6.1; Win64; x64)"
        headers = {"User-Agent": user_agent, "Content-Type": "text/xml"}

        uprn = kwargs.get("uprn")
        try:
            if uprn is None or uprn == "":
                raise ValueError("Invalid UPRN")
        except Exception as ex:
            print(f"Exception encountered: {ex}")
            print(
                "Please check the provided UPRN. If this error continues, please first trying setting the "
                "UPRN manually on line 115 before raising an issue."
            )

        # Make the Request - change the URL - find out your property number
        # URL
        url = "https://collections-torridge.azurewebsites.net/WebService2.asmx"
        # Post data
        post_data = (
            '<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><getRoundCalendarForUPRN xmlns="http://tempuri2.org/"><council>TOR</council><UPRN>'
            + uprn
            + "</UPRN><PW>wax01653</PW></getRoundCalendarForUPRN></soap:Body></soap:Envelope>"
        )
        requests.packages.urllib3.disable_warnings()
        page = requests.post(url, headers=headers, data=post_data)

        # Remove the soap wrapper
        namespaces = {
            "soap": "http://schemas.xmlsoap.org/soap/envelope/",
            "a": "http://tempuri2.org/",
        }
        dom = ElementTree.fromstring(page.text)
        page = dom.find(
            "./soap:Body"
            "/a:getRoundCalendarForUPRNResponse"
            "/a:getRoundCalendarForUPRNResult",
            namespaces,
        )
        # Make a BS4 object
        soup = BeautifulSoup(page.text, features="html.parser")
        soup.prettify()

        data = {"bins": []}

        b_el = soup.find("b", string="GardenBin")
        if b_el:
            results = re.search(
                "([A-Za-z]+ \\d\\d? [A-Za-z]+) (.*?)", b_el.next_sibling.split(": ")[1]
            )
            if results and results.groups()[0]:
                date = results.groups()[0] + " " + datetime.today().strftime("%Y")
                data["bins"].append(
                    {
                        "type": "GardenBin",
                        "collectionDate": get_next_occurrence_from_day_month(
                            datetime.strptime(date, "%a %d %b %Y")
                        ).strftime(date_format),
                    }
                )

        b_el = soup.find("b", string="Refuse")
        if b_el:
            results = re.search(
                "([A-Za-z]+ \\d\\d? [A-Za-z]+) (.*?)", b_el.next_sibling.split(": ")[1]
            )
            if results and results.groups()[0]:
                date = results.groups()[0] + " " + datetime.today().strftime("%Y")
                data["bins"].append(
                    {
                        "type": "Refuse",
                        "collectionDate": get_next_occurrence_from_day_month(
                            datetime.strptime(date, "%a %d %b %Y")
                        ).strftime(date_format),
                    }
                )

        b_el = soup.find("b", string="Recycling")
        if b_el:
            results = re.search(
                "([A-Za-z]+ \\d\\d? [A-Za-z]+) (.*?)", b_el.next_sibling.split(": ")[1]
            )
            if results and results.groups()[0]:
                date = results.groups()[0] + " " + datetime.today().strftime("%Y")
                data["bins"].append(
                    {
                        "type": "Recycling",
                        "collectionDate": get_next_occurrence_from_day_month(
                            datetime.strptime(date, "%a %d %b %Y")
                        ).strftime(date_format),
                    }
                )

        data["bins"].sort(
            key=lambda x: datetime.strptime(x.get("collectionDate"), date_format)
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
