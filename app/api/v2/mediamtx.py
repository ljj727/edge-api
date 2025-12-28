"""MediaMTX settings management API endpoints."""

import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.models.mediamtx_settings import MediaMTXSettings
from app.models.user import User
from app.schemas.mediamtx_settings import (
    MediaMTXConnectionTest,
    MediaMTXSettingsResponse,
    MediaMTXSettingsUpdate,
)
from app.services.stream_service import stream_service

router = APIRouter()
settings = get_settings()


def _sync_stream_service(db_settings: MediaMTXSettings) -> None:
    """Sync stream_service with DB settings."""
    stream_service.update_settings(
        api_url=db_settings.api_url,
        hls_url=db_settings.hls_url,
        webrtc_url=db_settings.webrtc_url,
        rtsp_url=db_settings.rtsp_url,
        enabled=db_settings.enabled,
    )


async def get_or_create_settings(db: AsyncSession) -> MediaMTXSettings:
    """Get existing settings or create with defaults from .env."""
    result = await db.execute(select(MediaMTXSettings).where(MediaMTXSettings.id == 1))
    db_settings = result.scalar_one_or_none()

    if not db_settings:
        # Create with defaults from .env
        db_settings = MediaMTXSettings(
            id=1,
            api_url=settings.mediamtx_api_url,
            hls_url=settings.mediamtx_hls_url,
            webrtc_url=settings.mediamtx_webrtc_url,
            rtsp_url=settings.mediamtx_rtsp_url,
            enabled=settings.mediamtx_enabled,
        )
        db.add(db_settings)
        await db.commit()
        await db.refresh(db_settings)
        logger.info("MediaMTX settings initialized from .env defaults")

    return db_settings


@router.get("", response_model=MediaMTXSettingsResponse)
async def get_mediamtx_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current MediaMTX connection settings.

    Returns settings from database, or creates defaults from .env if not exists.
    """
    db_settings = await get_or_create_settings(db)
    # Sync stream_service with DB settings
    _sync_stream_service(db_settings)
    return db_settings


@router.put("", response_model=MediaMTXSettingsResponse)
async def update_mediamtx_settings(
    request: MediaMTXSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update MediaMTX connection settings.

    Changes take effect immediately for new requests.
    """
    db_settings = await get_or_create_settings(db)

    # Update only provided fields
    if request.api_url is not None:
        db_settings.api_url = request.api_url
    if request.hls_url is not None:
        db_settings.hls_url = request.hls_url
    if request.webrtc_url is not None:
        db_settings.webrtc_url = request.webrtc_url
    if request.rtsp_url is not None:
        db_settings.rtsp_url = request.rtsp_url
    if request.enabled is not None:
        db_settings.enabled = request.enabled

    await db.commit()
    await db.refresh(db_settings)

    # Sync stream_service with new settings
    _sync_stream_service(db_settings)

    logger.info(f"MediaMTX settings updated by user {current_user.username}")
    return db_settings


@router.post("/reset", response_model=MediaMTXSettingsResponse)
async def reset_mediamtx_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reset MediaMTX settings to .env defaults.
    """
    db_settings = await get_or_create_settings(db)

    db_settings.api_url = settings.mediamtx_api_url
    db_settings.hls_url = settings.mediamtx_hls_url
    db_settings.webrtc_url = settings.mediamtx_webrtc_url
    db_settings.rtsp_url = settings.mediamtx_rtsp_url
    db_settings.enabled = settings.mediamtx_enabled

    await db.commit()
    await db.refresh(db_settings)

    # Sync stream_service with reset settings
    _sync_stream_service(db_settings)

    logger.info(f"MediaMTX settings reset to defaults by user {current_user.username}")
    return db_settings


@router.post("/test", response_model=MediaMTXConnectionTest)
async def test_mediamtx_connection(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Test connection to MediaMTX server.

    Returns success status, stream count, and latency.
    """
    db_settings = await get_or_create_settings(db)

    if not db_settings.enabled:
        return MediaMTXConnectionTest(
            success=False,
            message="MediaMTX integration is disabled",
        )

    try:
        start_time = time.time()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{db_settings.api_url}/paths/list",
                timeout=5.0,
            )
        latency_ms = (time.time() - start_time) * 1000

        if response.status_code == 200:
            data = response.json()
            streams_count = data.get("itemCount", 0)
            return MediaMTXConnectionTest(
                success=True,
                message="Connection successful",
                streams_count=streams_count,
                latency_ms=round(latency_ms, 2),
            )
        else:
            return MediaMTXConnectionTest(
                success=False,
                message=f"HTTP {response.status_code}: {response.text}",
            )

    except httpx.TimeoutException:
        return MediaMTXConnectionTest(
            success=False,
            message="Connection timeout",
        )
    except httpx.RequestError as e:
        return MediaMTXConnectionTest(
            success=False,
            message=f"Connection error: {str(e)}",
        )
