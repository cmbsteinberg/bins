import asyncio
import copy
from datetime import datetime
from time import time_ns

import httpx
from bs4 import BeautifulSoup

from api.compat.hacs import Collection  # type: ignore[attr-defined]

TITLE = "North Devon Council"
DESCRIPTION = "Source for northdevon.gov.uk waste collection."
URL = "https://www.northdevon.gov.uk"
TEST_CASES = {
    "Test_001": {"uprn": "100040249471", "postcode": "EX31 2LE"},
}

HOST = "https://my.northdevon.gov.uk"
AUTH_URL = f"{HOST}/authapi/isauthenticated?uri=https%253A%252F%252Fmy.northdevon.gov.uk%252Fservice%252FWasteRecyclingCollectionCalendar&hostname=my.northdevon.gov.uk&withCredentials=true"
API_URL = f"{HOST}/apibroker/runLookup"

USRN_LOOKUP_ID = "65141c7c38bd0"
TOKEN_LOOKUP_ID = "59e606ee95b7a"
DATE_RANGE_LOOKUP_ID = "6255925ca44cb"
SCHEDULE_LOOKUP_ID = "610943652e64f"
FULLADDR_LOOKUP_ID = "625587f465a91"

FORM_ID = "AF-Form-a9a357e7-8b6d-416e-b974-04a2aa857e87"
STAGE_ID = "AF-Stage-0e576350-a6e1-444e-a105-cb020f910845"

# Event lookups fired between schedule attempts. The first schedule call
# returns an empty shell; these populate the server-side state the repeat
# call renders into Results/Results2.
EVENT_LOOKUP_IDS = [
    "6256d7830063b",
    "6242ce0054bb1",
    "6241b13004ad9",
    "61091d927cd81",
    "6242ce0054bb1",
]

# Verbose AchieveForms address section, captured from a live browser session.
# The server only resolves the address when the search/selection fields
# (postcode_search, chooseAddress, uprnfromlookup, UPRNMF) arrive with their
# field metadata — a minimal qsUPRN-only form yields empty rows.
ADDRESS_TEMPLATE = {
    "qsUPRN": {
        "name": "qsUPRN",
        "type": "text",
        "id": "AF-Field-48df24fb-c7c5-4535-ad4c-1a156bbd317e",
        "value_changed": True,
        "section_id": "AF-Section-4bb0c928-3b8d-44e8-9ead-4434bf29cb97",
        "label": "querystring UPRN",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/qsUPRN",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "postcode_search": {
        "name": "postcode_search",
        "type": "text",
        "id": "AF-Field-c2edbc06-4adf-42ee-b81a-e9f271a34e30",
        "value_changed": True,
        "section_id": "AF-Section-4bb0c928-3b8d-44e8-9ead-4434bf29cb97",
        "label": "Postcode",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/postcode_search",
        "valid": True,
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": False,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "chooseAddress": {
        "name": "chooseAddress",
        "type": "select",
        "id": "AF-Field-4b196933-69f4-4a07-8dad-c698bb154486",
        "value_changed": True,
        "section_id": "AF-Section-4bb0c928-3b8d-44e8-9ead-4434bf29cb97",
        "label": "Choose address",
        "value_label": [],
        "hasOther": False,
        "value": "",
        "path": "root/chooseAddress",
        "valid": True,
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": False,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": "268024B3E6D318A27707353CAFAB7A4E8F1146F406761A20CA58A7045D64638F",
        "log_id": "70f1fd49-9b0a-4ec5-aeae-3d0966d275f2"
    },
    "uprnfromlookup": {
        "name": "uprnfromlookup",
        "type": "text",
        "id": "AF-Field-b7543679-3cac-43fa-9881-19c9cad745af",
        "value_changed": True,
        "section_id": "AF-Section-4bb0c928-3b8d-44e8-9ead-4434bf29cb97",
        "label": "uprn from lookup",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/uprnfromlookup",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": True,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "UPRNMF": {
        "name": "UPRNMF",
        "type": "text",
        "id": "AF-Field-87c34808-a70c-42ea-bfd6-7d1fb5ab2041",
        "value_changed": True,
        "section_id": "AF-Section-4bb0c928-3b8d-44e8-9ead-4434bf29cb97",
        "label": "UPRNMF",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/UPRNMF",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": True,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "FULLADDR2": {
        "name": "FULLADDR2",
        "type": "text",
        "id": "AF-Field-61c41172-7fc2-44cf-98c7-a9146444addd",
        "value_changed": True,
        "section_id": "AF-Section-4bb0c928-3b8d-44e8-9ead-4434bf29cb97",
        "label": "FULLADDR2",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/FULLADDR2",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    }
}


CALENDAR_TEMPLATE = {
    "FULLADDR": {
        "name": "FULLADDR",
        "type": "text",
        "id": "AF-Field-ca4ed0f3-9ab3-46f9-8c45-804c00041647",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "FULLADDR",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/FULLADDR",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": True,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "token": {
        "name": "token",
        "type": "text",
        "id": "AF-Field-5cdeca1c-cbff-4543-b583-d3eb1aee2c46",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "Token",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/token",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "uPRN": {
        "name": "uPRN",
        "type": "text",
        "id": "AF-Field-e299aa0a-3cfe-4307-bc47-112484b5f7ba",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "UPRN",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/uPRN",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "calstartDate": {
        "name": "calstartDate",
        "type": "date",
        "id": "AF-Field-9e3a360a-1ec0-4cf0-8cc6-dfa66021af5c",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "CalstartDate",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/calstartDate",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "calendDate": {
        "name": "calendDate",
        "type": "date",
        "id": "AF-Field-9a194a2a-8f3f-4538-b2ee-eb5a53bdd3f7",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "calendDate",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/calendDate",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "details": {
        "name": "details",
        "type": "subform",
        "id": "AF-Field-1ad0093d-d063-4e51-a9b5-47e3621d47d6",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "details",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/details",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": True,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "text1": {
        "name": "text1",
        "type": "textarea",
        "id": "AF-Field-4c158861-7274-48b0-8db4-794fd5ca90b0",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "text 1",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/text1",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "Results": {
        "name": "Results",
        "type": "text",
        "id": "AF-Field-7c6a74ed-8dfa-48ef-88e3-28a7ffc7696b",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "Results",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/Results",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "UPRN": {
        "name": "UPRN",
        "type": "text",
        "id": "AF-Field-86ea34f4-7294-4c18-ab3b-a98dec699d8e",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "UPRN1",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/UPRN",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "Alerts": {
        "name": "Alerts",
        "type": "text",
        "id": "AF-Field-a81c3e66-cddf-4366-bb4f-b559e43a4925",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "Dummy text area to hold alerts",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/Alerts",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "liveToken": {
        "name": "liveToken",
        "type": "text",
        "id": "AF-Field-021cd3c1-8da9-4da7-a76e-96c0c41a321f",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "liveToken",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/liveToken",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": True,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "Results2": {
        "name": "Results2",
        "type": "text",
        "id": "AF-Field-9ee01e23-579f-464c-badf-a1410ecd3567",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "Results2",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/Results2",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": True,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "USRN": {
        "name": "USRN",
        "type": "text",
        "id": "AF-Field-68d0f8ce-8de4-4cc6-b3b8-94b3dacd3940",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "USRN",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/USRN",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": True,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "streetEvents": {
        "name": "streetEvents",
        "type": "subform",
        "id": "AF-Field-68ab20b6-7349-4a44-a93f-239fe1ae92a3",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "Street Events",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/streetEvents",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": True,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "EventDescription": {
        "name": "EventDescription",
        "type": "text",
        "id": "AF-Field-d2f1abc1-2ccb-4153-9c92-d899f131b61c",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "EventDescription",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/EventDescription",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "EventDate": {
        "name": "EventDate",
        "type": "text",
        "id": "AF-Field-007a539d-ad88-435b-8985-581369096c4a",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "EventDate",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/EventDate",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "EventsDisplay": {
        "name": "EventsDisplay",
        "type": "text",
        "id": "AF-Field-e87ed67f-bcf9-4a8e-b4f3-592a0ac26de9",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "EventsDisplay",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/EventsDisplay",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "Comments": {
        "name": "Comments",
        "type": "text",
        "id": "AF-Field-b1b4813d-4a3b-444e-9123-218f823f40fe",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "Comments",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/Comments",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": False,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "OutText": {
        "name": "OutText",
        "type": "text",
        "id": "AF-Field-325df402-f806-41c0-8115-6f3e1fba8ef2",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "OutText",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/OutText",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": True,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "StartDate": {
        "name": "StartDate",
        "type": "date",
        "id": "AF-Field-1be87d33-59b2-492f-89c4-8532fc8142ef",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "StartDate",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/StartDate",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": True,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    },
    "EndDate": {
        "name": "EndDate",
        "type": "date",
        "id": "AF-Field-0beca980-b222-455d-90f2-5642056a7765",
        "value_changed": True,
        "section_id": "AF-Section-99707989-5aec-47f3-aa7c-32db80b759d9",
        "label": "EndDate",
        "value_label": "",
        "hasOther": False,
        "value": "",
        "path": "root/EndDate",
        "valid": "",
        "totals": "",
        "suffix": "",
        "prefix": "",
        "summary": "",
        "hidden": False,
        "_hidden": True,
        "isSummary": False,
        "staticMap": False,
        "isMandatory": True,
        "isRepeatable": False,
        "currencyPrefix": "",
        "decimalPlaces": "",
        "hash": ""
    }
}


def _full_post(uprn: str, postcode: str) -> dict:
    form = copy.deepcopy(ADDRESS_TEMPLATE)
    form["postcode_search"]["value"] = postcode.replace(" ", "")
    for key in ("chooseAddress", "uprnfromlookup", "UPRNMF"):
        form[key]["value"] = uprn
    return {
        "formId": FORM_ID,
        "stage_id": STAGE_ID,
        "formValues": {
            "Your address": form,
            "Calendar": copy.deepcopy(CALENDAR_TEMPLATE),
        },
    }
SCHEDULE_LOOKUP_ID = "610943652e64f"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{HOST}/fillform/?iframe_id=fillform-frame-1&db_id=",
}

ICON_MAP = {
    "Black Bin": "mdi:trash-can",
    "Green Bin": "mdi:leaf",
    "Recycling": "mdi:recycle",
    "Food": "mdi:food-apple",
    "Brown Bag": "mdi:recycle",
}


def _params(lookup_id: str, sid: str, **extra) -> dict:
    return {
        "id": lookup_id,
        "repeat_against": "",
        "noRetry": extra.get("noRetry", "true"),
        "getOnlyTokens": "undefined",
        "log_id": "",
        "app_name": "AF-Renderer::Self",
        "_": str(time_ns() // 1_000_000),
        "sid": sid,
    }


def _rows(resp_json: dict) -> dict:
    rows = resp_json.get("integration", {}).get("transformed", {}).get("rows_data", {})
    # First call triggers the lookup and returns [] — the retrieve call after
    # it returns the {"0": {...}} row dict.
    return rows if isinstance(rows, dict) else {}


async def _lookup(s, lookup_id: str, sid: str, form: dict, retries: int = 3) -> dict:
    """POST a runLookup until the "0" row appears (trigger then retrieve),
    echoing each row back into same-named form fields like AF-Renderer does —
    later calls render from that accumulated state."""
    for _ in range(retries):
        r = await s.post(
            API_URL,
            headers=HEADERS,
            params=_params(lookup_id, sid),
            json=form,
        )
        r.raise_for_status()
        row = _rows(r.json()).get("0", {})
        if row:
            _merge_row(form, row)
            return row
        await asyncio.sleep(2)
    return {}


def _merge_row(post: dict, row: dict) -> None:
    for section in post.get("formValues", {}).values():
        if not isinstance(section, dict):
            continue
        for field in section.values():
            if (
                isinstance(field, dict)
                and isinstance(row.get(field.get("name", "")), str)
            ):
                field["value"] = row[field["name"]]
                field["value_changed"] = True



def _parse_schedule_html(html: str) -> list[Collection]:
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    current_month = None
    current_year = None

    for li in soup.find_all("li"):
        if "MonthLabel" in li.get("class", []):
            h4 = li.find("h4")
            if h4 and h4.text.strip() != "Key":
                parts = h4.text.strip().split()
                if len(parts) == 2:
                    current_month = parts[0]
                    current_year = int(parts[1])
            continue

        if not current_month or not current_year:
            continue

        day_span = li.find("span", class_="wasteDay")
        type_span = li.find("span", class_="wasteType")
        if not day_span or not type_span:
            continue

        day = day_span.text.strip()
        bin_type = type_span.text.strip()
        try:
            dt = datetime.strptime(f"{day} {current_month} {current_year}", "%d %B %Y").date()
        except ValueError:
            continue

        icon = None
        for key, val in ICON_MAP.items():
            if key.lower() in bin_type.lower():
                icon = val
                break

        entries.append(Collection(date=dt, t=bin_type, icon=icon))

    return entries


class Source:
    def __init__(self, uprn: str | int, postcode: str | None = None):
        self._uprn = str(uprn)
        self._postcode = postcode or ""

    async def fetch(self) -> list[Collection]:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as s:
            r = await s.get(AUTH_URL, headers=HEADERS)
            r.raise_for_status()
            sid = r.json()["auth-session"]

            # Bootstrap the apibroker session. Without this call every
            # runLookup returns 403 {"result": "logout"}.
            r = await s.get(
                f"{HOST}/apibroker/domain/my.northdevon.gov.uk",
                headers=HEADERS,
                params={"_": str(time_ns() // 1_000_000), "sid": sid},
            )
            r.raise_for_status()

            post = _full_post(self._uprn, self._postcode)

            # Steps 1-3 advance the server-side form state (USRN, live
            # token, date range). The schedule call below reads that state.
            usrn = (await _lookup(s, USRN_LOOKUP_ID, sid, post)).get("USRN", "")
            if not usrn:
                return []
            token = (await _lookup(s, TOKEN_LOOKUP_ID, sid, post)).get("liveToken", "")
            r = await s.post(
                API_URL,
                headers=HEADERS,
                params=_params(FULLADDR_LOOKUP_ID, sid),
                json=post,
            )
            r.raise_for_status()
            date_row = await _lookup(s, DATE_RANGE_LOOKUP_ID, sid, post)
            post["formValues"]["Calendar"]["token"]["value"] = token
            post["formValues"]["Calendar"]["calstartDate"]["value"] = date_row.get(
                "calstartDate", ""
            )
            post["formValues"]["Calendar"]["calendDate"]["value"] = date_row.get(
                "calendDate", ""
            )

            # Step 4: get schedule HTML (may need two calls — first triggers, second retrieves)
            for _ in range(3):
                r = await s.post(
                    API_URL,
                    headers=HEADERS,
                    params=_params(SCHEDULE_LOOKUP_ID, sid, noRetry="true"),
                    json=post,
                )
                r.raise_for_status()
                row = _rows(r.json()).get("0", {})
                results_html = row.get("Results2", "")
                if results_html and "<h3>" in results_html:
                    break
                for event_id in EVENT_LOOKUP_IDS:
                    await _lookup(s, event_id, sid, post, retries=2)
                await asyncio.sleep(2)

        if not results_html or "<h3>" not in results_html:
            return []

        entries = _parse_schedule_html(results_html)
        return sorted(entries, key=lambda c: c.date)
