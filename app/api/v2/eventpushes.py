"""Eventpush (webhook) API endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DBSession
from app.schemas.eventpush import (
    EventpushCreate,
    EventpushDTO,
    EventpushStateUpdate,
    EventpushUpdate,
)
from app.schemas.protocol import ProtocolDTO
from app.services.eventpush_service import EventpushService

router = APIRouter()


@router.post("", response_model=EventpushDTO)
async def create_eventpush(
    data: EventpushCreate,
    db: DBSession,
) -> EventpushDTO:
    """
    Create event push webhook.

    - **name**: Webhook name
    - **url**: Webhook URL
    - **events**: List of event types to push
    - **enabled**: Whether webhook is enabled
    """
    eventpush_service = EventpushService(db)
    return await eventpush_service.create_eventpush(data)


@router.get("", response_model=list[EventpushDTO])
async def get_eventpushes(
    db: DBSession,
) -> list[EventpushDTO]:
    """Get all event push webhooks."""
    eventpush_service = EventpushService(db)
    return await eventpush_service.get_all_dto()


@router.put("/{eventpush_id}/events", response_model=EventpushDTO)
async def update_eventpush_events(
    eventpush_id: str,
    data: EventpushUpdate,
    db: DBSession,
) -> EventpushDTO:
    """
    Update eventpush events list.

    - **eventpush_id**: Eventpush ID
    - **events**: New list of event types
    """
    eventpush_service = EventpushService(db)
    result = await eventpush_service.update_events(eventpush_id, data.events)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eventpush not found",
        )

    return result


@router.put("/{eventpush_id}/state", response_model=EventpushStateUpdate)
async def update_eventpush_state(
    eventpush_id: str,
    data: EventpushStateUpdate,
    db: DBSession,
) -> EventpushStateUpdate:
    """
    Update eventpush enabled state.

    - **eventpush_id**: Eventpush ID
    - **enabled**: New enabled state
    """
    eventpush_service = EventpushService(db)
    result = await eventpush_service.update_state(eventpush_id, data.enabled)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eventpush not found",
        )

    return data


@router.delete("/{eventpush_id}")
async def delete_eventpush(
    eventpush_id: str,
    db: DBSession,
) -> dict:
    """
    Delete eventpush webhook.

    - **eventpush_id**: Eventpush ID to delete
    """
    eventpush_service = EventpushService(db)
    success = await eventpush_service.delete_by_id(eventpush_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eventpush not found",
        )

    return {"status": "success"}


@router.get("/protocol", response_model=ProtocolDTO | None)
async def get_eventpush_protocol(
    db: DBSession,
) -> ProtocolDTO | None:
    """Get eventhook protocol."""
    eventpush_service = EventpushService(db)
    return await eventpush_service.get_protocol()


@router.post("/protocol", response_model=ProtocolDTO)
async def create_eventpush_protocol(
    format_str: str,
    db: DBSession,
) -> ProtocolDTO:
    """Create or update eventhook protocol."""
    eventpush_service = EventpushService(db)
    return await eventpush_service.create_or_update_protocol(format_str)
