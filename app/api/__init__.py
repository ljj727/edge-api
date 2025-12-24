"""API router initialization."""

from fastapi import APIRouter

from app.api.v2 import router as v2_router

router = APIRouter()
router.include_router(v2_router, prefix="/api/v2")
