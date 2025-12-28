"""Camera schemas for API request/response validation."""

from datetime import datetime

from pydantic import BaseModel, Field


class CameraBase(BaseModel):
    """Base camera schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Camera display name")
    rtsp_url: str = Field(..., min_length=1, max_length=1024, description="RTSP URL for the stream")
    description: str | None = Field(None, max_length=1024, description="Optional description")
    location: str | None = Field(None, max_length=255, description="Camera location")
    manufacturer: str | None = Field(None, max_length=255, description="Camera manufacturer")
    model: str | None = Field(None, max_length=255, description="Camera model")


class CameraCreate(CameraBase):
    """Schema for creating a new camera."""

    id: str = Field(..., min_length=1, max_length=255, description="Unique camera ID (e.g., 'cam1')")


class CameraUpdate(BaseModel):
    """Schema for updating an existing camera."""

    name: str | None = Field(None, min_length=1, max_length=255)
    rtsp_url: str | None = Field(None, min_length=1, max_length=1024)
    description: str | None = Field(None, max_length=1024)
    location: str | None = Field(None, max_length=255)
    manufacturer: str | None = Field(None, max_length=255)
    model: str | None = Field(None, max_length=255)
    is_active: bool | None = None


class CameraResponse(CameraBase):
    """Schema for camera API response."""

    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    # Streaming URLs (generated dynamically)
    hls_url: str | None = None
    webrtc_url: str | None = None

    model_config = {"from_attributes": True}


class CameraStreamStatus(BaseModel):
    """Schema for camera stream status."""

    camera_id: str
    is_ready: bool
    is_connected: bool
    source_ready: bool | None = None
    readers_count: int | None = None
    error: str | None = None


class CameraListResponse(BaseModel):
    """Schema for camera list response."""

    cameras: list[CameraResponse]
    total: int


class CameraSyncResponse(BaseModel):
    """Schema for camera sync response."""

    success: bool
    message: str
    added: int = 0
    updated: int = 0
    deleted: int = 0
