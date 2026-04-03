
### Address Lookup (Client-Side, CORS)

User flow:
1. User enters Postcode
2. Address is returned (UPRN silently returned)
3. User selects address
4. Local Authroity is found
5. Bin time call is started

I need a python client that does the following:
1. Make an api call to the midsuffolk api below, using a postcode

FETCH
fetch("https://www.midsuffolk.gov.uk/api/jsonws/invoke", {
  "headers": {
    "accept": "*/*",
    "accept-language": "en-GB,en;q=0.9,en-US;q=0.8",
    "content-type": "text/plain;charset=UTF-8",
    "contenttype": "undefined",
    "priority": "u=1, i",
    "sec-ch-ua": "\"Chromium\";v=\"146\", \"Not-A.Brand\";v=\"24\", \"Microsoft Edge\";v=\"146\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"macOS\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "x-csrf-token": "Ba9vI91W"
  },
  "referrer": "https://www.midsuffolk.gov.uk/check-your-collection-day",
  "body": "{\"/placecube_digitalplace.addresscontext/search-address-by-postcode\":{\"companyId\":\"1486681\",\"postcode\":\"SW9 7AH\",\"fallbackToNationalLookup\":false}}",
  "method": "POST",
  "mode": "cors",
  "credentials": "include"
});
RESPONSE
[{"UPRN":"10008793671","addressLine1":"2","addressLine2":"RIDGEWAY ROAD","addressLine3":"","addressLine4":"","addressType":"PERSONAL","city":"LONDON","current":false,"fullAddress":"2 RIDGEWAY ROAD LONDON SW9 7AH","postcode":"SW9 7AH","source":"DPA"}]
2. Returns the fullAddress values to the user
3. Makes a GET request to https://api.postcodes.io/postcodes/{POSTCODE_NO_SPACE}
RESPONSE
{
  "status": 200,
  "result": {
    "postcode": "BR8 7RE",
    "quality": 1,
    "eastings": 551626,
    "northings": 170342,
    "country": "England",
    "nhs_ha": "South East Coast",
    "longitude": 0.178871,
    "latitude": 51.411831,
    "european_electoral_region": "South East",
    "primary_care_trust": "West Kent",
    "region": "South East",
    "lsoa": "Sevenoaks 001A",
    "msoa": "Sevenoaks 001",
    "incode": "7RE",
    "outcode": "BR8",
    "parliamentary_constituency": "Sevenoaks",
    "parliamentary_constituency_2024": "Sevenoaks",
    "admin_district": "Sevenoaks",
    "parish": "Hextable",
    "admin_county": "Kent",
    "date_of_introduction": "198001",
    "admin_ward": "Hextable",
    "ced": "Swanley",
    "ccg": "NHS Kent and Medway",
    "nuts": "Sevenoaks",
    "pfa": "Kent",
    "nhs_region": "South East",
    "ttwa": "Maidstone and North Kent",
    "national_park": null,
    "bua": "Swanley",
    "icb": "NHS Kent and Medway Integrated Care Board",
    "cancer_alliance": "Kent and Medway Cancer Alliance",
    "lsoa11": "Sevenoaks 001A",
    "msoa11": "Sevenoaks 001",
    "lsoa21": "Sevenoaks 001A",
    "msoa21": "Sevenoaks 001",
    "oa21": "E00058164",
    "ruc11": "Urban city and town",
    "ruc21": "Urban city and town",
    "lep1": "South East",
    "lep2": null,
    "codes": {
      "admin_district": "E07000111",
      "admin_county": "E10000016",
      "admin_ward": "E05009960",
      "parish": "E04012394",
      "parliamentary_constituency": "E14001465",
      "parliamentary_constituency_2024": "E14001465",
      "ccg": "E38000237",
      "ccg_id": "91Q",
      "ced": "E58000739",
      "nuts": "TLJ46",
      "lsoa": "E01024445",
      "msoa": "E02005087",
      "lau2": "E07000111",
      "pfa": "E23000032",
      "nhs_region": "E40000005",
      "ttwa": "E30000188",
      "national_park": null,
      "bua": "E34001422",
      "icb": "E54000032",
      "cancer_alliance": "E56000004",
      "lsoa11": "E01024445",
      "msoa11": "E02005087",
      "lsoa21": "E01024445",
      "msoa21": "E02005087",
      "oa21": "E00058164",
      "ruc11": "C1",
      "ruc21": "C1",
      "lep1": "E37000025",
      "lep2": null
    }
  }
}
4. Rteurns admin_county and admin_district
5. Matches admin_county/ admin_districtto scraper in scrapers/
We need a static mapping of admin_county -> scraper. We can use https://hub.arcgis.com/api/v3/datasets/1b80e7fe67e34cf5b084ba23700d7974_0/downloads/data?format=csv&spatialRefId=4326&where=1%3D1 along with thefuzz to match scrapers to council/district names. This should be auto-generated at commit, creating a json map

