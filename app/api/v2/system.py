"""System API endpoints."""

from fastapi import APIRouter

from app.core.config import get_dx_config, get_settings
from app.core.deps import CurrentUserRequired
from app.schemas.system import SystemInfo

settings = get_settings()

router = APIRouter()


@router.get("", response_model=SystemInfo)
async def get_system_info(
    current_user: CurrentUserRequired,
) -> SystemInfo:
    """Get system info with JWT claims."""
    dx_config = get_dx_config()

    return SystemInfo(
        id=current_user.id,
        name=current_user.username,
        address=None,  # Could be populated from config
        dx_id=None,  # From license
        license_type=None,  # From license
        end_date=None,  # From license
        license_key=None,  # From license
        version=settings.app_version,
        framework="FastAPI",
        capacity=None,  # From license
        activated=False,  # From license check
        nats_port=dx_config.nats_port,
        launcher_port=dx_config.launcher_port,
    )
