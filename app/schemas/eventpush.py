"""Eventpush (webhook) schemas for API request/response."""

from pydantic import BaseModel, Field

from app.schemas.event import EventObject


class EventpushCreate(BaseModel):
    """Eventpush creation schema."""

    name: str
    url: str
    events: list[str] = []
    enabled: bool = True


class EventpushDTO(BaseModel):
    """Eventpush response schema."""

    id: str
    name: str
    url: str
    events: list[str] = []
    enabled: bool = True

    model_config = {"from_attributes": True}


class EventpushUpdate(BaseModel):
    """Eventpush events update schema."""

    events: list[str]


class EventpushStateUpdate(BaseModel):
    """Eventpush state update schema."""

    enabled: bool


class EventpushEventMsgStream(BaseModel):
    """Eventpush event message stream info."""

    app_id: str = Field(..., alias="app_id")
    stream_id: str = Field(..., alias="stream_id")

    model_config = {"populate_by_name": True}


class EventpushEventMsg(BaseModel):
    """Eventpush event message payload."""

    id: int
    stream: EventpushEventMsgStream
    timestamp: int
    event_type: str
    desc: str | None = None
    objects: list[EventObject] = []
