"""Camera management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.camera import Camera
from app.models.user import User
from app.schemas.camera import (
    CameraCreate,
    CameraListResponse,
    CameraResponse,
    CameraStreamStatus,
    CameraSyncResponse,
    CameraUpdate,
)
from app.services.stream_service import stream_service

router = APIRouter()


@router.post("/sync", response_model=CameraSyncResponse)
async def sync_cameras_from_mediamtx(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sync cameras from MediaMTX to database.

    Fetches all streams from MediaMTX and syncs them to the Camera table:
    - New streams → added
    - Changed streams → updated
    - Removed streams → deleted
    """
    # Get all streams from MediaMTX
    streams = await stream_service.get_all_paths()

    # Get existing cameras from DB
    result = await db.execute(select(Camera))
    existing_cameras = {c.id: c for c in result.scalars().all()}

    added = 0
    updated = 0
    deleted = 0
    stream_ids = set()

    for stream in streams:
        stream_name = stream.get("name", "")
        if not stream_name:
            continue

        stream_ids.add(stream_name)
        rtsp_url = stream_service.get_rtsp_url(stream_name)
        is_ready = stream.get("ready", False)

        if stream_name in existing_cameras:
            # Update existing camera if changed
            camera = existing_cameras[stream_name]
            changed = False

            if camera.rtsp_url != rtsp_url:
                camera.rtsp_url = rtsp_url
                changed = True
            if camera.is_active != is_ready:
                camera.is_active = is_ready
                changed = True

            if changed:
                updated += 1
                logger.info(f"Camera {stream_name} updated")
        else:
            # Add new camera
            camera = Camera(
                id=stream_name,
                name=stream_name,
                rtsp_url=rtsp_url,
                is_active=is_ready,
            )
            db.add(camera)
            added += 1
            logger.info(f"Camera {stream_name} added from MediaMTX")

    # Delete cameras not in MediaMTX
    for camera_id, camera in existing_cameras.items():
        if camera_id not in stream_ids:
            await db.delete(camera)
            deleted += 1
            logger.info(f"Camera {camera_id} deleted (not in MediaMTX)")

    await db.commit()

    message = f"Sync completed: {added} added, {updated} updated, {deleted} deleted"
    logger.info(message)

    return CameraSyncResponse(
        success=True,
        message=message,
        added=added,
        updated=updated,
        deleted=deleted,
    )


def _camera_to_response(camera: Camera) -> CameraResponse:
    """Convert Camera model to response schema with streaming URLs."""
    return CameraResponse(
        id=camera.id,
        name=camera.name,
        rtsp_url=camera.rtsp_url,
        description=camera.description,
        location=camera.location,
        manufacturer=camera.manufacturer,
        model=camera.model,
        is_active=camera.is_active,
        created_at=camera.created_at,
        updated_at=camera.updated_at,
        hls_url=stream_service.get_hls_url(camera.id),
        webrtc_url=stream_service.get_webrtc_url(camera.id),
    )


@router.post("", response_model=CameraResponse, status_code=201)
async def create_camera(
    request: CameraCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Register a new IP camera.

    - **id**: Unique camera identifier (e.g., "cam1", "front-door")
    - **name**: Display name for the camera
    - **rtsp_url**: RTSP stream URL (e.g., "rtsp://admin:password@192.168.1.100:554/stream")
    """
    # Check for duplicate ID
    result = await db.execute(select(Camera).where(Camera.id == request.id))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Camera with ID '{request.id}' already exists",
        )

    # Register with MediaMTX (best effort - don't fail if MediaMTX is unavailable)
    success = await stream_service.register_camera(request.id, request.rtsp_url)
    if not success:
        logger.warning(f"MediaMTX registration failed for camera {request.id}, continuing anyway")

    # Create camera in database
    camera = Camera(
        id=request.id,
        name=request.name,
        rtsp_url=request.rtsp_url,
        description=request.description,
        location=request.location,
        manufacturer=request.manufacturer,
        model=request.model,
    )
    db.add(camera)
    await db.commit()
    await db.refresh(camera)

    logger.info(f"Camera {camera.id} created by user {current_user.username}")
    return _camera_to_response(camera)


@router.get("", response_model=CameraListResponse)
async def list_cameras(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get list of all registered cameras.

    Returns cameras with their streaming URLs (HLS and WebRTC).
    """
    query = select(Camera).order_by(Camera.created_at.desc())

    if is_active is not None:
        query = query.where(Camera.is_active == is_active)

    # Get total count
    count_result = await db.execute(select(Camera))
    total = len(count_result.scalars().all())

    # Get paginated results
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    cameras = result.scalars().all()

    return CameraListResponse(
        cameras=[_camera_to_response(c) for c in cameras],
        total=total,
    )


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get details of a specific camera.

    Includes streaming URLs for HLS and WebRTC playback.
    """
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    return _camera_to_response(camera)


@router.put("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: str,
    request: CameraUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update camera information.

    If RTSP URL is changed, the stream will be updated in MediaMTX.
    """
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Update RTSP URL in MediaMTX if changed (best effort)
    if request.rtsp_url and request.rtsp_url != camera.rtsp_url:
        success = await stream_service.update_camera(camera_id, request.rtsp_url)
        if not success:
            logger.warning(f"MediaMTX update failed for camera {camera_id}, continuing anyway")
        camera.rtsp_url = request.rtsp_url

    # Update other fields if provided
    if request.name is not None:
        camera.name = request.name
    if request.description is not None:
        camera.description = request.description
    if request.location is not None:
        camera.location = request.location
    if request.manufacturer is not None:
        camera.manufacturer = request.manufacturer
    if request.model is not None:
        camera.model = request.model
    if request.is_active is not None:
        camera.is_active = request.is_active

    await db.commit()
    await db.refresh(camera)

    logger.info(f"Camera {camera_id} updated by user {current_user.username}")
    return _camera_to_response(camera)


@router.delete("/{camera_id}")
async def delete_camera(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a camera and remove its stream from MediaMTX.
    """
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Remove from MediaMTX
    await stream_service.unregister_camera(camera_id)

    # Delete from database
    await db.delete(camera)
    await db.commit()

    logger.info(f"Camera {camera_id} deleted by user {current_user.username}")
    return {"success": True, "message": f"Camera '{camera_id}' deleted"}


@router.get("/{camera_id}/status", response_model=CameraStreamStatus)
async def get_camera_status(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the streaming status of a camera from MediaMTX.

    Returns information about stream readiness and connected viewers.
    """
    # Verify camera exists
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Get status from MediaMTX
    status = await stream_service.get_stream_status(camera_id)

    return CameraStreamStatus(
        camera_id=camera_id,
        is_ready=status.get("is_ready", False),
        is_connected=status.get("status") == "ok",
        source_ready=status.get("source_ready"),
        readers_count=status.get("readers_count"),
        error=status.get("message") if status.get("status") == "error" else None,
    )


@router.post("/{camera_id}/restart")
async def restart_camera_stream(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Restart the camera stream by re-registering with MediaMTX.
    """
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Unregister and re-register (best effort)
    await stream_service.unregister_camera(camera_id)
    success = await stream_service.register_camera(camera_id, camera.rtsp_url)

    if not success:
        logger.warning(f"MediaMTX restart failed for camera {camera_id}")
        return {"success": False, "message": f"MediaMTX unavailable for camera '{camera_id}'"}

    logger.info(f"Camera {camera_id} stream restarted by user {current_user.username}")
    return {"success": True, "message": f"Camera '{camera_id}' stream restarted"}
