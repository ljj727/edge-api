"""Statistics API endpoints."""

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Query
from loguru import logger
from sqlalchemy import func, select

from app.core.deps import CurrentUserRequired, DBSession
from app.models.camera import Camera
from app.models.event import Event
from app.schemas.statistics import (
    EventLogItem,
    EventLogResponse,
    EventTypesResponse,
    SummaryItem,
    SummaryResponse,
    TrendResponse,
    TrendSeries,
)

router = APIRouter()


def _timestamp_to_iso(ts_ms: int) -> str:
    """Convert millisecond timestamp to ISO 8601 string."""
    return datetime.utcfromtimestamp(ts_ms / 1000).isoformat() + "Z"


def _date_to_timestamp_range(
    date_str: str, unit: str
) -> tuple[int, int, str, str]:
    """
    Convert date string to timestamp range based on unit.

    Returns: (start_ts_ms, end_ts_ms, start_date_str, end_date_str)
    """
    if unit == "day":
        # date_str: "2024-12-28"
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        start = dt
        end = dt + timedelta(days=1)
    elif unit == "month":
        # date_str: "2024-12"
        dt = datetime.strptime(date_str + "-01", "%Y-%m-%d")
        start = dt
        # Next month
        if dt.month == 12:
            end = dt.replace(year=dt.year + 1, month=1)
        else:
            end = dt.replace(month=dt.month + 1)
    elif unit == "quarter":
        # date_str: "2024-Q4"
        year, quarter = date_str.split("-Q")
        quarter = int(quarter)
        start_month = (quarter - 1) * 3 + 1
        start = datetime(int(year), start_month, 1)
        # Next quarter
        end_month = start_month + 3
        if end_month > 12:
            end = datetime(int(year) + 1, 1, 1)
        else:
            end = datetime(int(year), end_month, 1)
    else:  # year
        # date_str: "2024"
        year = int(date_str)
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)

    start_ts = int(start.timestamp() * 1000)
    end_ts = int(end.timestamp() * 1000)
    start_date_str = start.strftime("%Y-%m-%d")
    end_date_str = (end - timedelta(days=1)).strftime("%Y-%m-%d")

    return start_ts, end_ts, start_date_str, end_date_str


def _generate_example_events() -> list[EventLogItem]:
    """Generate example events for testing."""
    now = datetime.utcnow()
    examples = []

    event_types = ["vehicle", "person", "animal"]
    cameras = [
        ("cam1", "Front Gate"),
        ("cam2", "Parking Lot"),
        ("cam3", "Entrance"),
    ]

    for i in range(10):
        ts = now - timedelta(hours=i * 2, minutes=i * 5)
        cam_id, cam_name = cameras[i % len(cameras)]
        event_type = event_types[i % len(event_types)]

        examples.append(EventLogItem(
            id=f"evt_{1000 + i}",
            camera_id=cam_id,
            camera_name=cam_name,
            event_type=event_type,
            timestamp=ts.isoformat() + "Z",
            video_url=f"/video/events/{1000 + i}.mp4" if i % 3 == 0 else None,
            thumbnail_url=f"/media/events/{1000 + i}/thumbnail.jpg" if i % 2 == 0 else None,
        ))

    return examples


def _generate_example_summary(
    unit: str, date: str
) -> list[SummaryItem]:
    """Generate example summary for testing."""
    _, _, start_date, end_date = _date_to_timestamp_range(date, unit)

    return [
        SummaryItem(
            camera_id="cam1",
            camera_name="Front Gate",
            event_type="vehicle",
            start_date=start_date,
            end_date=end_date,
            count=145,
        ),
        SummaryItem(
            camera_id="cam1",
            camera_name="Front Gate",
            event_type="person",
            start_date=start_date,
            end_date=end_date,
            count=87,
        ),
        SummaryItem(
            camera_id="cam2",
            camera_name="Parking Lot",
            event_type="vehicle",
            start_date=start_date,
            end_date=end_date,
            count=312,
        ),
        SummaryItem(
            camera_id="cam2",
            camera_name="Parking Lot",
            event_type="person",
            start_date=start_date,
            end_date=end_date,
            count=56,
        ),
    ]


def _generate_example_trend(
    unit: str, date: str
) -> TrendResponse:
    """Generate example trend data for testing."""
    import random

    if unit == "day":
        labels = [f"{h}:00" for h in range(24)]
    elif unit == "month":
        # Get days in month
        _, end_ts, _, _ = _date_to_timestamp_range(date, unit)
        end_dt = datetime.utcfromtimestamp(end_ts / 1000)
        days = (end_dt - timedelta(days=1)).day
        labels = [str(d) for d in range(1, days + 1)]
    elif unit == "quarter":
        labels = ["Month 1", "Month 2", "Month 3"]
    else:  # year
        labels = ["Q1", "Q2", "Q3", "Q4"]

    # Generate random data
    n = len(labels)
    vehicle_data = [random.randint(5, 50) for _ in range(n)]
    person_data = [random.randint(2, 30) for _ in range(n)]
    animal_data = [random.randint(0, 10) for _ in range(n)]
    total_data = [v + p + a for v, p, a in zip(vehicle_data, person_data, animal_data)]

    return TrendResponse(
        unit=unit,
        date=date,
        labels=labels,
        series=[
            TrendSeries(event_type="total", data=total_data),
            TrendSeries(event_type="vehicle", data=vehicle_data),
            TrendSeries(event_type="person", data=person_data),
            TrendSeries(event_type="animal", data=animal_data),
        ],
    )


@router.get("/events", response_model=EventLogResponse)
async def get_event_log(
    db: DBSession,
    current_user: CurrentUserRequired,
    camera_id: str | None = Query(None),
    event_type: str | None = Query(None),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> EventLogResponse:
    """
    Get paginated event log.

    - **camera_id**: Filter by camera ID (optional)
    - **event_type**: Filter by event type (optional)
    - **from**: Start date ISO format (optional)
    - **to**: End date ISO format (optional)
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 10, max: 100)
    """
    # Build query
    query = select(Event).order_by(Event.timestamp.desc())
    count_query = select(func.count()).select_from(Event)

    # Apply filters
    if camera_id:
        query = query.where(Event.video_id == camera_id)
        count_query = count_query.where(Event.video_id == camera_id)

    if event_type:
        query = query.where(Event.object_type == event_type)
        count_query = count_query.where(Event.object_type == event_type)

    if from_date:
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        from_ts = int(from_dt.timestamp() * 1000)
        query = query.where(Event.timestamp >= from_ts)
        count_query = count_query.where(Event.timestamp >= from_ts)

    if to_date:
        to_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
        to_ts = int(to_dt.timestamp() * 1000)
        query = query.where(Event.timestamp < to_ts)
        count_query = count_query.where(Event.timestamp < to_ts)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # If no events, return example data
    if total == 0:
        examples = _generate_example_events()
        return EventLogResponse(
            items=examples,
            total=len(examples),
            page=1,
            page_size=page_size,
        )

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    events = result.scalars().all()

    # Get camera names
    camera_ids = list(set(e.video_id for e in events if e.video_id))
    camera_names = {}
    if camera_ids:
        cameras_result = await db.execute(
            select(Camera).where(Camera.id.in_(camera_ids))
        )
        for cam in cameras_result.scalars().all():
            camera_names[cam.id] = cam.name or cam.id

    # Map to response
    items = []
    for event in events:
        items.append(EventLogItem(
            id=str(event.id),
            camera_id=event.video_id or "",
            camera_name=camera_names.get(event.video_id, event.video_name or event.video_id or ""),
            event_type=event.object_type or "unknown",
            timestamp=_timestamp_to_iso(event.timestamp),
            video_url=None,  # TODO: Generate video clip URL if available
            thumbnail_url=f"/media/events/{event.id}/thumbnail.jpg" if event.id else None,
        ))

    return EventLogResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    db: DBSession,
    current_user: CurrentUserRequired,
    unit: Literal["day", "month", "quarter", "year"] = Query(...),
    date: str = Query(..., description="Date based on unit: day=2024-12-28, month=2024-12, quarter=2024-Q4, year=2024"),
    camera_id: str | None = Query(None),
    event_type: str | None = Query(None),
) -> SummaryResponse:
    """
    Get aggregated statistics summary.

    - **unit**: Time unit (day, month, quarter, year)
    - **date**: Date string based on unit
    - **camera_id**: Filter by camera ID (optional)
    - **event_type**: Filter by event type (optional)
    """
    start_ts, end_ts, start_date_str, end_date_str = _date_to_timestamp_range(date, unit)

    # Build aggregation query
    query = (
        select(
            Event.video_id,
            Event.video_name,
            Event.object_type,
            func.count().label("count"),
        )
        .where(Event.timestamp >= start_ts)
        .where(Event.timestamp < end_ts)
        .group_by(Event.video_id, Event.video_name, Event.object_type)
    )

    if camera_id:
        query = query.where(Event.video_id == camera_id)

    if event_type:
        query = query.where(Event.object_type == event_type)

    result = await db.execute(query)
    rows = result.all()

    # If no data, return example
    if not rows:
        return SummaryResponse(items=_generate_example_summary(unit, date))

    # Get camera names
    camera_ids = list(set(row.video_id for row in rows if row.video_id))
    camera_names = {}
    if camera_ids:
        cameras_result = await db.execute(
            select(Camera).where(Camera.id.in_(camera_ids))
        )
        for cam in cameras_result.scalars().all():
            camera_names[cam.id] = cam.name or cam.id

    # Map to response
    items = []
    for row in rows:
        items.append(SummaryItem(
            camera_id=row.video_id or "",
            camera_name=camera_names.get(row.video_id, row.video_name or row.video_id or ""),
            event_type=row.object_type or "unknown",
            start_date=start_date_str,
            end_date=end_date_str,
            count=row.count,
        ))

    return SummaryResponse(items=items)


@router.get("/trend", response_model=TrendResponse)
async def get_trend(
    db: DBSession,
    current_user: CurrentUserRequired,
    unit: Literal["day", "month", "quarter", "year"] = Query(...),
    date: str = Query(..., description="Date based on unit"),
    camera_id: str | None = Query(None),
    event_type: str | None = Query(None),
) -> TrendResponse:
    """
    Get trend data for charts.

    - **unit**: Time unit (day, month, quarter, year)
    - **date**: Date string based on unit
    - **camera_id**: Filter by camera ID (optional)
    - **event_type**: Filter by event type (optional)
    """
    start_ts, end_ts, _, _ = _date_to_timestamp_range(date, unit)

    # Determine time buckets based on unit
    if unit == "day":
        # 24 hourly buckets
        bucket_count = 24
        bucket_size_ms = 3600 * 1000  # 1 hour
        labels = [f"{h}:00" for h in range(24)]
    elif unit == "month":
        # Days in month
        end_dt = datetime.utcfromtimestamp(end_ts / 1000)
        days = (end_dt - timedelta(days=1)).day
        bucket_count = days
        bucket_size_ms = 86400 * 1000  # 1 day
        labels = [str(d) for d in range(1, days + 1)]
    elif unit == "quarter":
        # 3 monthly buckets
        bucket_count = 3
        # Variable bucket size - handle separately
        labels = ["Month 1", "Month 2", "Month 3"]
    else:  # year
        # 4 quarterly buckets
        bucket_count = 4
        # Variable bucket size - handle separately
        labels = ["Q1", "Q2", "Q3", "Q4"]

    # Build base query
    base_query = (
        select(Event.timestamp, Event.object_type)
        .where(Event.timestamp >= start_ts)
        .where(Event.timestamp < end_ts)
    )

    if camera_id:
        base_query = base_query.where(Event.video_id == camera_id)

    if event_type:
        base_query = base_query.where(Event.object_type == event_type)

    result = await db.execute(base_query)
    events = result.all()

    # If no data, return example
    if not events:
        return _generate_example_trend(unit, date)

    # Initialize buckets
    event_types_found = set()
    buckets: dict[str, list[int]] = {}

    for event in events:
        ts = event.timestamp
        et = event.object_type or "unknown"
        event_types_found.add(et)

        if et not in buckets:
            buckets[et] = [0] * bucket_count

        # Calculate bucket index
        if unit in ("day", "month"):
            bucket_idx = min((ts - start_ts) // bucket_size_ms, bucket_count - 1)
        elif unit == "quarter":
            # Month within quarter
            dt = datetime.utcfromtimestamp(ts / 1000)
            bucket_idx = (dt.month - 1) % 3
        else:  # year
            # Quarter within year
            dt = datetime.utcfromtimestamp(ts / 1000)
            bucket_idx = (dt.month - 1) // 3

        buckets[et][int(bucket_idx)] += 1

    # Build series with total
    series = []
    total_data = [0] * bucket_count

    for et in sorted(event_types_found):
        data = buckets.get(et, [0] * bucket_count)
        series.append(TrendSeries(event_type=et, data=data))
        for i, val in enumerate(data):
            total_data[i] += val

    # Add total series at the beginning
    series.insert(0, TrendSeries(event_type="total", data=total_data))

    return TrendResponse(
        unit=unit,
        date=date,
        labels=labels,
        series=series,
    )


@router.get("/event-types", response_model=EventTypesResponse)
async def get_event_types(
    db: DBSession,
    current_user: CurrentUserRequired,
) -> EventTypesResponse:
    """
    Get list of available event types.
    """
    # Query distinct event types
    result = await db.execute(
        select(Event.object_type)
        .distinct()
        .where(Event.object_type.isnot(None))
    )
    types = [row[0] for row in result.all() if row[0]]

    # If no data, return example types
    if not types:
        types = ["vehicle", "person", "animal", "fire", "smoke"]

    return EventTypesResponse(event_types=sorted(types))
