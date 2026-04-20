from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("api.reports")

router = APIRouter()


class ReportRequest(BaseModel):
    postcode: str
    address: str
    uprn: str
    council: str
    collections: list[dict]


@router.post("/report")
async def report_wrong(body: ReportRequest):
    collections_text = ", ".join(
        f"{c.get('type', '?')} ({c.get('date', '?')})" for c in body.collections
    )
    logger.warning(
        "User report: postcode=%s council=%s uprn=%s address=%s collections=[%s]",
        body.postcode,
        body.council,
        body.uprn,
        body.address,
        collections_text,
    )
    return {"status": "logged"}
