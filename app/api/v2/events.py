"""Event API endpoints."""

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.deps import DBSession
from app.schemas.event import (
    EventPagedResponse,
    EventQueryParams,
    EventSummaryResponse,
    EventTrendResponse,
)
from app.schemas.protocol import ProtocolDTO
from app.services.event_service import EventService

router = APIRouter()


@router.get("", response_model=EventPagedResponse)
async def get_events(
    db: DBSession,
    app_id: str | None = Query(None, alias="appId"),
    event_setting_id: str | None = Query(None, alias="eventSettingId"),
    event_setting_name: str | None = Query(None, alias="eventSettingName"),
    video_id: str | None = Query(None, alias="videoId"),
    video_name: str | None = Query(None, alias="videoName"),
    device_id: str | None = Query(None, alias="deviceId"),
    vms_id: str | None = Query(None, alias="vmsId"),
    object_type: str | None = Query(None, alias="objectType"),
    start_time: int = Query(0, alias="startTime"),
    end_time: int = Query(0, alias="endTime"),
    paging_size: int = Query(10, alias="pagingSize", ge=0),
    paging_index: int = Query(1, alias="pagingIndex", ge=1),
    order: str = Query("desc"),
) -> EventPagedResponse:
    """
    Search events with pagination.

    - **appId**: Filter by application ID
    - **eventSettingId**: Filter by event setting ID
    - **videoId**: Filter by video/camera ID
    - **objectType**: Filter by detected object type (person, car, etc.)
    - **startTime**: Unix timestamp (ms) start range
    - **endTime**: Unix timestamp (ms) end range
    - **pagingSize**: Items per page (0 = all)
    - **pagingIndex**: Page number (1-based)
    - **order**: Sort order (asc/desc)
    """
    params = EventQueryParams(
        app_id=app_id,
        event_setting_id=event_setting_id,
        event_setting_name=event_setting_name,
        video_id=video_id,
        video_name=video_name,
        device_id=device_id,
        vms_id=vms_id,
        object_type=object_type,
        start_time=start_time,
        end_time=end_time,
        paging_size=paging_size,
        paging_index=paging_index,
        order=order,
    )

    event_service = EventService(db)
    return await event_service.get_events(params)


@router.get("/default")
async def get_events_default(
    db: DBSession,
    app_id: str | None = Query(None, alias="appId"),
    video_id: str | None = Query(None, alias="videoId"),
    object_type: str | None = Query(None, alias="objectType"),
    start_time: int = Query(0, alias="startTime"),
    end_time: int = Query(0, alias="endTime"),
    paging_size: int = Query(10, alias="pagingSize", ge=0),
    paging_index: int = Query(1, alias="pagingIndex", ge=1),
    order: str = Query("desc"),
) -> list:
    """Get events in default protocol format."""
    params = EventQueryParams(
        app_id=app_id,
        video_id=video_id,
        object_type=object_type,
        start_time=start_time,
        end_time=end_time,
        paging_size=paging_size,
        paging_index=paging_index,
        order=order,
    )

    event_service = EventService(db)
    result = await event_service.get_events(params)

    # Transform using protocol
    protocol = await event_service.get_protocol("eventpolling")
    return await event_service.transform_events_with_protocol(result.events, protocol)


@router.get("/protocol", response_model=ProtocolDTO | None)
async def get_event_protocol(
    db: DBSession,
) -> ProtocolDTO | None:
    """Get event polling protocol."""
    event_service = EventService(db)
    return await event_service.get_protocol("eventpolling")


@router.post("/protocol", response_model=ProtocolDTO)
async def create_event_protocol(
    format_str: str,
    db: DBSession,
) -> ProtocolDTO:
    """Create or update event polling protocol."""
    event_service = EventService(db)
    return await event_service.create_or_update_protocol("eventpolling", format_str)


@router.get("/{event_id}/image")
async def get_event_image(
    event_id: int,
    db: DBSession,
) -> Response:
    """Get event image by event ID."""
    event_service = EventService(db)
    image_data = await event_service.get_event_image(event_id)

    if not image_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    return Response(
        content=image_data,
        media_type="image/jpeg",
    )


@router.get("/summary", response_model=EventSummaryResponse)
async def get_event_summary(
    db: DBSession,
    video_id: str | None = Query(None, alias="videoId"),
    object_type: str | None = Query(None, alias="objectType"),
    start_time: int = Query(0, alias="startTime"),
    end_time: int = Query(0, alias="endTime"),
) -> EventSummaryResponse:
    """
    Get event summary grouped by camera and type.

    - **videoId**: Filter by video/camera ID
    - **objectType**: Filter by detected object type
    - **startTime**: Unix timestamp (ms) start range
    - **endTime**: Unix timestamp (ms) end range
    """
    params = EventQueryParams(
        video_id=video_id,
        object_type=object_type,
        start_time=start_time,
        end_time=end_time,
    )

    event_service = EventService(db)
    return await event_service.get_event_summary(params)


@router.get("/trend", response_model=EventTrendResponse)
async def get_event_trend(
    db: DBSession,
    video_id: str | None = Query(None, alias="videoId"),
    object_type: str | None = Query(None, alias="objectType"),
    start_time: int = Query(0, alias="startTime"),
    end_time: int = Query(0, alias="endTime"),
    unit: str = Query("hour"),
) -> EventTrendResponse:
    """
    Get event trend (time-series) data.

    - **videoId**: Filter by video/camera ID
    - **objectType**: Filter by detected object type
    - **startTime**: Unix timestamp (ms) start range
    - **endTime**: Unix timestamp (ms) end range
    - **unit**: Aggregation unit (hour, day, month, year)
    """
    params = EventQueryParams(
        video_id=video_id,
        object_type=object_type,
        start_time=start_time,
        end_time=end_time,
    )

    event_service = EventService(db)
    return await event_service.get_event_trend(params, unit)
