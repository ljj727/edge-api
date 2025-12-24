"""Video schemas for API request/response."""

from pydantic import BaseModel, Field


class VideoSettings(BaseModel):
    """Video settings schema."""

    masking_region: list[list[list[float]]] = Field(
        default_factory=list, alias="maskingRegion"
    )
    detection_point: str = Field("c:b", alias="detectionPoint")
    line_cross_point: str = Field("c:c", alias="lineCrossPoint")

    model_config = {"populate_by_name": True}


class VideoCreate(BaseModel):
    """Video creation schema."""

    id: str | None = None
    uri: str
    name: str | None = None
    device_id: str | None = Field(None, alias="deviceId")
    server_id: str | None = Field(None, alias="serverId")
    settings: VideoSettings | None = None

    model_config = {"populate_by_name": True}


class VideoDTO(BaseModel):
    """Video response schema."""

    id: str
    uri: str
    name: str | None = None
    device_id: str | None = Field(None, alias="deviceId")
    server_id: str | None = Field(None, alias="serverId")
    settings: VideoSettings | None = None

    model_config = {"populate_by_name": True, "from_attributes": True}


class VideoUpdate(BaseModel):
    """Video update schema (name only)."""

    name: str | None = None


class VideoSettingUpdate(BaseModel):
    """Video settings update schema."""

    settings: VideoSettings
