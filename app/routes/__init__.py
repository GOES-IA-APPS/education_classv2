from fastapi import APIRouter

from app.routes.phase3 import router as phase3_router
from app.routes.web import router as web_router

router = APIRouter()
router.include_router(web_router)
router.include_router(phase3_router)

__all__ = ["router"]
