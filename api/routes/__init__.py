from fastapi import APIRouter

from api.routes.lookup import router as lookup_router
from api.routes.meta import router as meta_router
from api.routes.report import router as report_router

router = APIRouter()
router.include_router(lookup_router)
router.include_router(meta_router)
router.include_router(report_router)
