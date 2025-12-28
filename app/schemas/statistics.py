"""Statistics schemas for API request/response."""

from pydantic import BaseModel


# Event Log
class EventLogItem(BaseModel):
    """Individual event log item."""

    id: str
    camera_id: str
    camera_name: str
    event_type: str
    timestamp: str  # ISO 8601
    video_url: str | None = None
    thumbnail_url: str | None = None


class EventLogResponse(BaseModel):
    """Paginated event log response."""

    items: list[EventLogItem]
    total: int
    page: int
    page_size: int


# Summary
class SummaryItem(BaseModel):
    """Summary item for aggregated statistics."""

    camera_id: str
    camera_name: str
    event_type: str
    start_date: str
    end_date: str
    count: int


class SummaryResponse(BaseModel):
    """Summary response with aggregated items."""

    items: list[SummaryItem]


# Trend
class TrendSeries(BaseModel):
    """Single series for trend chart."""

    event_type: str
    data: list[int]


class TrendResponse(BaseModel):
    """Trend chart data response."""

    unit: str  # 'day' | 'month' | 'quarter' | 'year'
    date: str
    labels: list[str]
    series: list[TrendSeries]


# Event Types
class EventTypesResponse(BaseModel):
    """Available event types response."""

    event_types: list[str]
