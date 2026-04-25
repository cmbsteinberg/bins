from datetime import datetime

from api.compat.hacs import Collection  # type: ignore[attr-defined]
from api.compat.hacs.service.WhitespaceWRP import WhitespaceClient

TITLE = "Waverley Borough Council"
DESCRIPTION = "Source for www.waverley.gov.uk services for Waverley Borough Council."
URL = "https://waverley.gov.uk"
TEST_CASES = {
    "Example": {
        "postcode": "GU8 5QQ",
        "house_number": "1",
        "street": "Gasden Drive",
    },
    "Example No Postcode Space": {
        "postcode": "GU85QQ",
        "house_number": "1",
        "street": "Gasden Drive",
    },
}
ICON_MAP = {
    "Domestic Waste": "mdi:trash-can",
    "Recycling": "mdi:recycle",
    "Garden Waste": "mdi:leaf",
    "Food Waste": "mdi:food-apple",
}

API_URL = "https://wav-wrp.whitespacews.com/"


class Source:
    def __init__(
        self,
        house_number=None,
        street=None,
        town=None,
        postcode=None,
    ):
        self._house_number = house_number
        self._street = street
        self._town = town
        self._postcode = postcode
        self._client = WhitespaceClient(API_URL)

    async def fetch(self):
        schedule = await self._client.fetch_schedule(
            address_name_number=self._house_number,
            postcode=self._postcode,
            street=self._street,
            town=self._town,
        )

        entries = []
        for date_str, type_str in schedule:
            collection_type = type_str.replace(" Collection Service", "")
            entries.append(
                Collection(
                    date=datetime.strptime(date_str, "%d/%m/%Y").date(),
                    t=type_str,
                    icon=ICON_MAP.get(collection_type),
                )
            )
        return entries
