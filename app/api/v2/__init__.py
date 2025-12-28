"""API v2 router initialization."""

from fastapi import APIRouter

from app.api.v2.apps import router as apps_router
from app.api.v2.auth import router as auth_router
from app.api.v2.cameras import router as cameras_router
from app.api.v2.mediamtx import router as mediamtx_router
from app.api.v2.streams import router as streams_router
from app.api.v2.eventpushes import router as eventpushes_router
from app.api.v2.events import router as events_router
from app.api.v2.inference import router as inference_router
from app.api.v2.license import router as license_router
from app.api.v2.media import router as media_router
from app.api.v2.metrics import router as metrics_router
from app.api.v2.mx import router as mx_router
from app.api.v2.registry import router as registry_router
from app.api.v2.sensors import router as sensors_router
from app.api.v2.statistics import router as statistics_router
from app.api.v2.system import router as system_router
from app.api.v2.users import router as users_router
from app.api.v2.videos import router as videos_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(users_router, prefix="/users", tags=["Users"])
router.include_router(apps_router, prefix="/apps", tags=["Apps"])
router.include_router(videos_router, prefix="/videos", tags=["Videos"])
router.include_router(cameras_router, prefix="/cameras", tags=["Cameras"])
router.include_router(streams_router, prefix="/streams", tags=["Streams"])
router.include_router(inference_router, prefix="/inference", tags=["Inference"])
router.include_router(events_router, prefix="/events", tags=["Events"])
router.include_router(eventpushes_router, prefix="/eventpushes", tags=["Eventpushes"])
router.include_router(mx_router, prefix="/mx", tags=["Mx"])
router.include_router(mediamtx_router, prefix="/mediamtx", tags=["MediaMTX"])
router.include_router(registry_router, prefix="/registry", tags=["Registry"])
router.include_router(media_router, prefix="/media", tags=["Media"])
router.include_router(system_router, prefix="/system", tags=["System"])
router.include_router(license_router, prefix="/license", tags=["License"])
router.include_router(metrics_router, prefix="/metrics", tags=["Metrics"])
router.include_router(sensors_router, prefix="/sensors", tags=["Sensors"])
router.include_router(statistics_router, prefix="/statistics", tags=["Statistics"])
