"""Event schemas for API request/response."""

from pydantic import BaseModel, Field, field_validator


class EventObjectClassifier(BaseModel):
    """Event object classifier schema."""

    type: str | None = None
    label: str | None = None


class EventObject(BaseModel):
    """Event detected object schema."""

    track_id: str | None = Field(None, alias="trackId")
    label: str | None = None
    bbox: list[float] | None = None  # [x, y, w, h]
    classifiers: list[EventObjectClassifier] = []
    score: float | None = None

    model_config = {"populate_by_name": True}


class EventCreate(BaseModel):
    """Event creation schema."""

    event_setting_id: str | None = Field(None, alias="eventSettingId")
    event_setting_name: str | None = Field(None, alias="eventSettingName")
    video_id: str | None = Field(None, alias="videoId")
    video_name: str | None = Field(None, alias="videoName")
    app_id: str | None = Field(None, alias="appId")
    timestamp: int
    caption: str | None = None
    desc: str | None = None
    device_id: str | None = Field(None, alias="deviceId")
    vms_id: str | None = Field(None, alias="vmsId")
    objects: list[EventObject] = []

    model_config = {"populate_by_name": True}


class EventDTO(BaseModel):
    """Event response schema."""

    id: int
    event_setting_id: str | None = Field(None, alias="eventSettingId")
    event_setting_name: str | None = Field(None, alias="eventSettingName")
    video_id: str | None = Field(None, alias="videoId")
    video_name: str | None = Field(None, alias="videoName")
    app_id: str | None = Field(None, alias="appId")
    timestamp: int
    caption: str | None = None
    desc: str | None = None
    device_id: str | None = Field(None, alias="deviceId")
    vms_id: str | None = Field(None, alias="vmsId")
    objects: list[EventObject] = []
    object_type: str | None = Field(None, alias="objectType")

    model_config = {"populate_by_name": True, "from_attributes": True}

    @field_validator("timestamp", mode="before")
    @classmethod
    def normalize_timestamp(cls, v: int | None) -> int:
        """Normalize timestamp to 13-digit milliseconds."""
        if v is None:
            return 0
        ts_str = str(v)
        if len(ts_str) == 10:  # seconds
            return v * 1000
        elif len(ts_str) == 16:  # microseconds
            return v // 1000
        return v


class EventQueryParams(BaseModel):
    """Event query parameters schema."""

    app_id: str | None = Field(None, alias="appId")
    event_setting_id: str | None = Field(None, alias="eventSettingId")
    event_setting_name: str | None = Field(None, alias="eventSettingName")
    video_id: str | None = Field(None, alias="videoId")
    video_name: str | None = Field(None, alias="videoName")
    device_id: str | None = Field(None, alias="deviceId")
    vms_id: str | None = Field(None, alias="vmsId")
    object_type: str | None = Field(None, alias="objectType")
    start_time: int = Field(0, alias="startTime")
    end_time: int = Field(0, alias="endTime")
    paging_size: int = Field(10, alias="pagingSize", ge=0)
    paging_index: int = Field(1, alias="pagingIndex", ge=1)
    order: str = "desc"

    model_config = {"populate_by_name": True}


class EventPagedResponse(BaseModel):
    """Paginated event response schema."""

    events: list[EventDTO]
    total: int
    offset: int
    limit: int


class EventSummaryItem(BaseModel):
    """Event summary item schema."""

    camera: str | None = None
    video_id: str | None = Field(None, alias="videoId")
    type: str | None = None
    start: int | None = None
    end: int | None = None
    count: int = 0

    model_config = {"populate_by_name": True}


class EventSummaryResponse(BaseModel):
    """Event summary response schema."""

    items: list[EventSummaryItem]
    total: int
    offset: int
    limit: int


class EventTrendResponse(BaseModel):
    """Event trend (time-series) response schema."""

    categories: list[str]  # Time labels
    series: dict[str, list[int]]  # type -> counts per category
    total: list[int]  # Sum per category
