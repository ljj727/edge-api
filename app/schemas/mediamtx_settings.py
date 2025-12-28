"""MediaMTX settings schemas for API request/response validation."""

from datetime import datetime

from pydantic import BaseModel, Field


class MediaMTXSettingsBase(BaseModel):
    """Base MediaMTX settings schema."""

    api_url: str = Field(..., description="MediaMTX REST API URL (e.g., http://host:9997/v3)")
    hls_url: str = Field(..., description="MediaMTX HLS streaming URL (e.g., http://host:8888)")
    webrtc_url: str = Field(..., description="MediaMTX WebRTC URL (e.g., http://host:8889)")
    rtsp_url: str = Field(..., description="MediaMTX RTSP URL (e.g., rtsp://host:8554)")
    enabled: bool = Field(default=True, description="Enable MediaMTX integration")


class MediaMTXSettingsUpdate(BaseModel):
    """Schema for updating MediaMTX settings."""

    api_url: str | None = Field(None, description="MediaMTX REST API URL")
    hls_url: str | None = Field(None, description="MediaMTX HLS streaming URL")
    webrtc_url: str | None = Field(None, description="MediaMTX WebRTC URL")
    rtsp_url: str | None = Field(None, description="MediaMTX RTSP URL")
    enabled: bool | None = Field(None, description="Enable MediaMTX integration")


class MediaMTXSettingsResponse(MediaMTXSettingsBase):
    """Schema for MediaMTX settings response."""

    id: int
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class MediaMTXConnectionTest(BaseModel):
    """Schema for connection test response."""

    success: bool
    message: str
    streams_count: int | None = None
    latency_ms: float | None = None
