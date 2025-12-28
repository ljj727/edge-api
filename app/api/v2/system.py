"""System API endpoints."""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import nats
import psutil
from fastapi import APIRouter, HTTPException
from loguru import logger
from sqlalchemy import delete, func, select

from app.core.config import get_dx_config, get_settings
from app.core.deps import CurrentUserRequired, DBSession
from app.grpc import get_grpc_client
from app.models.app import App
from app.models.camera import Camera
from app.models.event import Event
from app.models.image import Image
from app.models.inference import Inference
from app.models.eventpush import Eventpush
from app.schemas.system import (
    CleanupResponse,
    ServiceHealth,
    SyncAllResponse,
    SyncResult,
    SystemHealthResponse,
    SystemInfo,
    SystemStatusResponse,
)
from app.services.stream_service import stream_service

settings = get_settings()
_start_time = time.time()

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


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    current_user: CurrentUserRequired,
    db: DBSession,
) -> SystemHealthResponse:
    """
    Check health of all connected services.

    Returns status of Core (gRPC), MediaMTX, NATS, and Database.
    """
    # Check Core (gRPC)
    core_health = ServiceHealth(status="disconnected")
    grpc_client = get_grpc_client()
    if grpc_client:
        try:
            start = time.time()
            await grpc_client.get_dx_info()
            latency = (time.time() - start) * 1000
            core_health = ServiceHealth(status="connected", latency_ms=round(latency, 2))
        except Exception as e:
            core_health = ServiceHealth(status="error", message=str(e))

    # Check MediaMTX
    mediamtx_health = ServiceHealth(status="disconnected")
    try:
        start = time.time()
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{stream_service.api_url}/paths/list", timeout=5.0)
            latency = (time.time() - start) * 1000
            if resp.status_code == 200:
                data = resp.json()
                mediamtx_health = ServiceHealth(
                    status="connected",
                    latency_ms=round(latency, 2),
                    details={"streams": data.get("itemCount", 0)},
                )
            else:
                mediamtx_health = ServiceHealth(status="error", message=f"HTTP {resp.status_code}")
    except Exception as e:
        mediamtx_health = ServiceHealth(status="error", message=str(e))

    # Check NATS
    nats_health = ServiceHealth(status="disconnected")
    try:
        start = time.time()
        nc = await nats.connect(settings.nats_uri, connect_timeout=3)
        latency = (time.time() - start) * 1000
        await nc.close()
        nats_health = ServiceHealth(status="connected", latency_ms=round(latency, 2))
    except Exception as e:
        nats_health = ServiceHealth(status="error", message=str(e))

    # Check Database
    db_health = ServiceHealth(status="disconnected")
    try:
        start = time.time()
        await db.execute(select(func.count()).select_from(App))
        latency = (time.time() - start) * 1000
        db_health = ServiceHealth(status="connected", latency_ms=round(latency, 2))
    except Exception as e:
        db_health = ServiceHealth(status="error", message=str(e))

    # Overall health
    all_connected = all(
        s.status == "connected"
        for s in [core_health, mediamtx_health, nats_health, db_health]
    )

    return SystemHealthResponse(
        healthy=all_connected,
        core=core_health,
        mediamtx=mediamtx_health,
        nats=nats_health,
        database=db_health,
    )


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    current_user: CurrentUserRequired,
    db: DBSession,
) -> SystemStatusResponse:
    """
    Get system status summary.

    Returns counts of apps, cameras, inferences, events, and disk usage.
    """
    # Count apps
    apps_result = await db.execute(select(func.count()).select_from(App))
    apps_count = apps_result.scalar() or 0

    # Count cameras
    cameras_result = await db.execute(select(func.count()).select_from(Camera))
    cameras_count = cameras_result.scalar() or 0

    # Count active inferences
    inferences_result = await db.execute(select(func.count()).select_from(Inference))
    active_inferences = inferences_result.scalar() or 0

    # Count total events
    events_result = await db.execute(select(func.count()).select_from(Event))
    total_events = events_result.scalar() or 0

    # Count pending eventpushes (enabled ones)
    eventpushes_result = await db.execute(
        select(func.count()).select_from(Eventpush).where(Eventpush.enabled == True)
    )
    pending_eventpushes = eventpushes_result.scalar() or 0

    # Get disk usage
    try:
        disk = psutil.disk_usage(settings.data_save_folder)
        disk_usage_percent = disk.percent
    except Exception:
        disk_usage_percent = 0.0

    # Calculate uptime
    uptime_seconds = int(time.time() - _start_time)

    return SystemStatusResponse(
        apps_count=apps_count,
        cameras_count=cameras_count,
        active_inferences=active_inferences,
        total_events=total_events,
        pending_eventpushes=pending_eventpushes,
        disk_usage_percent=disk_usage_percent,
        uptime_seconds=uptime_seconds,
    )


@router.post("/sync-all", response_model=SyncAllResponse)
async def sync_all(
    current_user: CurrentUserRequired,
    db: DBSession,
) -> SyncAllResponse:
    """
    Sync all data from external services.

    Runs cameras, apps, and inferences sync in sequence.
    """
    results = []

    # Import sync functions
    from app.api.v2.cameras import sync_cameras_from_mediamtx
    from app.api.v2.apps import sync_apps_from_core
    from app.api.v2.inference import sync_inferences

    # 1. Sync cameras from MediaMTX
    try:
        camera_result = await sync_cameras_from_mediamtx(db=db, current_user=current_user)
        results.append(SyncResult(
            name="cameras",
            success=camera_result.success,
            added=camera_result.added,
            updated=camera_result.updated,
            deleted=camera_result.deleted,
            message=camera_result.message,
        ))
    except Exception as e:
        logger.error(f"Camera sync failed: {e}")
        results.append(SyncResult(name="cameras", success=False, message=str(e)))

    # 2. Sync apps from Core
    try:
        apps_result = await sync_apps_from_core(db=db, current_user=current_user)
        results.append(SyncResult(
            name="apps",
            success=apps_result.success,
            added=apps_result.added,
            updated=apps_result.updated,
            deleted=apps_result.deleted,
            message=apps_result.message,
        ))
    except HTTPException as e:
        logger.error(f"Apps sync failed: {e.detail}")
        results.append(SyncResult(name="apps", success=False, message=e.detail))
    except Exception as e:
        logger.error(f"Apps sync failed: {e}")
        results.append(SyncResult(name="apps", success=False, message=str(e)))

    # 3. Sync inferences
    try:
        inference_result = await sync_inferences(db=db, current_user=current_user)
        results.append(SyncResult(
            name="inferences",
            success=inference_result.success,
            added=inference_result.added_to_db + inference_result.added_to_core,
            deleted=inference_result.deleted_from_db,
            message=inference_result.message,
        ))
    except HTTPException as e:
        logger.error(f"Inference sync failed: {e.detail}")
        results.append(SyncResult(name="inferences", success=False, message=e.detail))
    except Exception as e:
        logger.error(f"Inference sync failed: {e}")
        results.append(SyncResult(name="inferences", success=False, message=str(e)))

    all_success = all(r.success for r in results)
    total_added = sum(r.added for r in results)
    total_deleted = sum(r.deleted for r in results)

    return SyncAllResponse(
        success=all_success,
        message=f"Sync completed: {total_added} added, {total_deleted} deleted",
        results=results,
    )


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_old_data(
    current_user: CurrentUserRequired,
    db: DBSession,
    days: int = 30,
) -> CleanupResponse:
    """
    Clean up old events and images based on retention policy.

    - **days**: Delete data older than this many days (default: 30)
    """
    if days < 1:
        raise HTTPException(status_code=400, detail="days must be at least 1")

    cutoff_timestamp = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

    # Get images to delete (for disk space calculation)
    images_result = await db.execute(
        select(Image).where(Image.timestamp < cutoff_timestamp)
    )
    old_images = images_result.scalars().all()

    # Calculate disk space to be freed
    disk_freed_bytes = 0
    images_deleted = 0
    for img in old_images:
        try:
            img_path = Path(img.path)
            if img_path.exists():
                disk_freed_bytes += img_path.stat().st_size
                img_path.unlink()
            images_deleted += 1
        except Exception as e:
            logger.warning(f"Failed to delete image {img.path}: {e}")

    # Delete old images from DB
    await db.execute(delete(Image).where(Image.timestamp < cutoff_timestamp))

    # Delete old events
    events_result = await db.execute(
        select(func.count()).select_from(Event).where(Event.timestamp < cutoff_timestamp)
    )
    events_to_delete = events_result.scalar() or 0

    await db.execute(delete(Event).where(Event.timestamp < cutoff_timestamp))

    await db.commit()

    disk_freed_mb = round(disk_freed_bytes / (1024 * 1024), 2)

    message = f"Cleanup completed: {events_to_delete} events, {images_deleted} images deleted"
    logger.info(message)

    return CleanupResponse(
        success=True,
        message=message,
        events_deleted=events_to_delete,
        images_deleted=images_deleted,
        disk_freed_mb=disk_freed_mb,
    )
