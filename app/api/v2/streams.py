"""Stream management API endpoints - Direct MediaMTX integration."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.models.user import User
from app.services.stream_service import stream_service

router = APIRouter()


class StreamUrls(BaseModel):
    """Streaming URLs for different protocols."""

    rtsp: str | None = None
    hls: str
    whep: str
    whep_player: str


class StreamInfo(BaseModel):
    """Stream information from MediaMTX."""

    name: str
    ready: bool
    source_ready: bool | None = None
    source_type: str | None = None
    readers_count: int = 0
    urls: StreamUrls


class StreamListResponse(BaseModel):
    """Response for stream list."""

    streams: list[StreamInfo]
    total: int


class SyncResponse(BaseModel):
    """Response for sync operation."""

    success: bool
    message: str
    synced_count: int = 0


@router.get("", response_model=StreamListResponse)
async def list_streams(
    current_user: User = Depends(get_current_user),
):
    """
    Get all streams directly from MediaMTX.

    Returns stream information with WebRTC/HLS URLs for playback.
    This endpoint queries MediaMTX directly without database lookup.
    """
    paths = await stream_service.get_all_paths()

    streams = []
    for path in paths:
        name = path.get("name", "")
        if not name:
            continue

        # Get source info
        source = path.get("source", {}) or {}

        streams.append(
            StreamInfo(
                name=name,
                ready=path.get("ready", False),
                source_ready=path.get("sourceReady"),
                source_type=source.get("type") if source else None,
                readers_count=len(path.get("readers", [])),
                urls=StreamUrls(
                    rtsp=stream_service.get_rtsp_url(name),
                    hls=stream_service.get_hls_url(name),
                    whep=stream_service.get_webrtc_url(name),
                    whep_player=stream_service.get_webrtc_player_url(name),
                ),
            )
        )

    logger.info(f"Retrieved {len(streams)} streams from MediaMTX")
    return StreamListResponse(streams=streams, total=len(streams))


@router.get("/{stream_name}", response_model=StreamInfo)
async def get_stream(
    stream_name: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get details of a specific stream from MediaMTX.

    Returns stream status and playback URLs.
    """
    status = await stream_service.get_stream_status(stream_name)

    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Stream '{stream_name}' not found")

    if status.get("status") == "error":
        raise HTTPException(status_code=503, detail=status.get("message", "MediaMTX error"))

    return StreamInfo(
        name=stream_name,
        ready=status.get("is_ready", False),
        source_ready=status.get("source_ready"),
        source_type=status.get("source"),
        readers_count=status.get("readers_count", 0),
        urls=StreamUrls(
            rtsp=stream_service.get_rtsp_url(stream_name),
            hls=stream_service.get_hls_url(stream_name),
            whep=stream_service.get_webrtc_url(stream_name),
            whep_player=stream_service.get_webrtc_player_url(stream_name),
        ),
    )


@router.get("/{stream_name}/player-url")
async def get_player_url(
    stream_name: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get the WebRTC player URL for embedding in iframe or direct access.
    """
    return {
        "stream_name": stream_name,
        "whep_player": stream_service.get_webrtc_player_url(stream_name),
        "whep": stream_service.get_webrtc_url(stream_name),
        "hls": stream_service.get_hls_url(stream_name),
    }


@router.get("/health/check")
async def check_mediamtx_health():
    """
    Check MediaMTX server health status.
    No authentication required for health checks.
    """
    health = await stream_service.health_check()
    return health
