"""Inference schemas for API request/response."""

from pydantic import BaseModel, Field


class InferenceSettingConfigTarget(BaseModel):
    """Inference setting config target schema."""

    labels: list[str] = []
    classifiers: dict[str, list[str]] = {}


class InferenceSettingConfig(BaseModel):
    """Inference setting config schema."""

    event_type: str | None = Field(None, alias="eventType")
    event_setting_id: str | None = Field(None, alias="eventSettingId")
    event_setting_name: str | None = Field(None, alias="eventSettingName")
    parent_id: str | None = Field(None, alias="parentId")
    points: list[list[float]] = []  # Polygon points
    target: InferenceSettingConfigTarget | None = None
    timeout: int | None = None
    ncond: int | None = None
    direction: str | None = None
    in_order: bool | None = Field(None, alias="inOrder")
    turn: str | None = None
    ext: dict | None = None
    detection_point: str | None = Field(None, alias="detectionPoint")

    model_config = {"populate_by_name": True}


class InferenceSettings(BaseModel):
    """Inference settings schema."""

    version: str = "1.6.1"
    configs: list[InferenceSettingConfig] = []


class InferenceCreate(BaseModel):
    """Inference creation schema."""

    app_id: str = Field(..., alias="appId")
    video_id: str = Field(..., alias="videoId")
    uri: str
    name: str | None = None
    type: str | None = None
    settings: InferenceSettings | None = None
    node_settings: dict | None = Field(None, alias="nodeSettings")

    model_config = {"populate_by_name": True}


class InferenceDTO(BaseModel):
    """Inference response schema."""

    app_id: str = Field(..., alias="appId")
    video_id: str = Field(..., alias="videoId")
    uri: str
    name: str | None = None
    type: str | None = None
    settings: InferenceSettings | None = None
    node_settings: dict | None = Field(None, alias="nodeSettings")

    model_config = {"populate_by_name": True, "from_attributes": True}


class InferenceEventSettingUpdate(BaseModel):
    """Inference event setting update schema."""

    settings: InferenceSettings


class InferenceWithStatus(BaseModel):
    """Inference with status schema."""

    app_id: str = Field(..., alias="appId")
    video_id: str = Field(..., alias="videoId")
    status: int = 0  # NG=0, READY=1, CONNECTING=2, CONNECTED=3
    count: int = 0  # Event count
    eos: bool = False
    err: bool = False

    model_config = {"populate_by_name": True}


class InferenceStreamStart(BaseModel):
    """Inference stream start response schema."""

    location: str
    ts_start: int
    session_id: str
