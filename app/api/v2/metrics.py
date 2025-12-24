"""Metrics API endpoints."""

import platform

import psutil

from fastapi import APIRouter

from app.core.deps import CurrentUserRequired
from app.schemas.system import MetricsResponse

router = APIRouter()


def _get_disk_path() -> str:
    """Get the appropriate disk path for the OS."""
    if platform.system() == "Darwin":
        # macOS APFS: actual data is on /System/Volumes/Data
        data_path = "/System/Volumes/Data"
        try:
            psutil.disk_usage(data_path)
            return data_path
        except Exception:
            pass
    return "/"


@router.get("", response_model=MetricsResponse)
async def get_metrics(
    current_user: CurrentUserRequired,
) -> MetricsResponse:
    """
    Get system metrics (CPU, memory, disk usage).

    Returns real-time system metrics using psutil.
    """
    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.1)

    # Memory
    memory = psutil.virtual_memory()

    # Disk (use correct path for macOS)
    disk = psutil.disk_usage(_get_disk_path())

    return MetricsResponse(
        cpu_percent=cpu_percent,
        memory_total=memory.total,
        memory_used=memory.used,
        memory_percent=memory.percent,
        disk_total=disk.total,
        disk_used=disk.used,
        disk_percent=disk.percent,
    )
