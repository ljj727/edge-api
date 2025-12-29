"""Event service for detection event management."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.event import Event
from app.models.image import Image
from app.models.protocol import Protocol
from app.schemas.event import (
    EventDTO,
    EventObject,
    EventPagedResponse,
    EventQueryParams,
    EventSummaryItem,
    EventSummaryResponse,
    EventTrendResponse,
)
from app.schemas.protocol import ProtocolDTO
from app.services.base_service import BaseService

settings = get_settings()


class EventService(BaseService[Event]):
    """Event service for detection event operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Event)

    async def save_event_from_nats(self, data: dict[str, Any]) -> list[Event]:
        """Save events received from NATS to database.

        NATS event format from EC:
        {
            "metadata": {
                "streamId": str,  # → video_id
                "vmsId": str,
                "appId": str,
                "timestamp": int (nanoseconds)
            },
            "events": [
                {
                    "eventSettingId": str,
                    "eventSettingName": str,
                    "objects": [{"trackId": int, "label": str, "bbox": {...}, "score": float}],
                    "caption": str,
                    "description": str
                }
            ]
        }
        """
        metadata = data.get("metadata", {})
        events_data = data.get("events", [])

        # Extract common metadata
        video_id = metadata.get("streamId")
        vms_id = metadata.get("vmsId")
        app_id = metadata.get("appId")
        # Convert nanoseconds to milliseconds
        timestamp_ns = metadata.get("timestamp", 0)
        timestamp_ms = timestamp_ns // 1_000_000 if timestamp_ns > 0 else 0

        saved_events = []
        for event_data in events_data:
            event = Event(
                event_setting_id=event_data.get("eventSettingId"),
                event_setting_name=event_data.get("eventSettingName"),
                video_id=video_id,
                video_name=video_id,  # Use streamId as video_name if not provided
                app_id=app_id,
                timestamp=timestamp_ms,
                caption=event_data.get("caption"),
                desc=event_data.get("description"),
                device_id=None,
                vms_id=vms_id,
            )

            # Set objects and extract object_type
            objects = event_data.get("objects", [])
            event.set_objects(objects)

            self.db.add(event)
            saved_events.append(event)

        await self.db.commit()
        for event in saved_events:
            await self.db.refresh(event)

        return saved_events

    async def get_events(self, params: EventQueryParams) -> EventPagedResponse:
        """Get paginated events with filters."""
        query = select(Event)

        # Apply filters
        filters = []
        if params.app_id:
            filters.append(Event.app_id == params.app_id)
        if params.event_setting_id:
            filters.append(Event.event_setting_id == params.event_setting_id)
        if params.event_setting_name:
            filters.append(Event.event_setting_name == params.event_setting_name)
        if params.video_id:
            filters.append(Event.video_id == params.video_id)
        if params.video_name:
            filters.append(Event.video_name == params.video_name)
        if params.device_id:
            filters.append(Event.device_id == params.device_id)
        if params.vms_id:
            filters.append(Event.vms_id == params.vms_id)
        if params.object_type:
            filters.append(Event.object_type == params.object_type)
        if params.start_time > 0:
            filters.append(Event.timestamp >= params.start_time)
        if params.end_time > 0:
            filters.append(Event.timestamp <= params.end_time)

        if filters:
            query = query.where(and_(*filters))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply ordering
        if params.order.lower() == "asc":
            query = query.order_by(Event.timestamp)
        else:
            query = query.order_by(desc(Event.timestamp))

        # Apply pagination
        offset = (params.paging_index - 1) * params.paging_size
        if params.paging_size > 0:
            query = query.offset(offset).limit(params.paging_size)

        result = await self.db.execute(query)
        events = list(result.scalars().all())

        return EventPagedResponse(
            events=[self._to_dto(e) for e in events],
            total=total,
            offset=offset,
            limit=params.paging_size,
        )

    async def get_event_summary(
        self,
        params: EventQueryParams,
    ) -> EventSummaryResponse:
        """Get event summary grouped by camera and type."""
        query = select(
            Event.video_id,
            Event.video_name,
            Event.object_type,
            func.min(Event.timestamp).label("start"),
            func.max(Event.timestamp).label("end"),
            func.count().label("count"),
        )

        # Apply filters
        filters = []
        if params.video_id:
            filters.append(Event.video_id == params.video_id)
        if params.object_type:
            filters.append(Event.object_type == params.object_type)
        if params.start_time > 0:
            filters.append(Event.timestamp >= params.start_time)
        if params.end_time > 0:
            filters.append(Event.timestamp <= params.end_time)

        if filters:
            query = query.where(and_(*filters))

        query = query.group_by(Event.video_id, Event.video_name, Event.object_type)

        result = await self.db.execute(query)
        rows = result.all()

        items = [
            EventSummaryItem(
                camera=row.video_name,
                video_id=row.video_id,
                type=row.object_type,
                start=row.start,
                end=row.end,
                count=row.count,
            )
            for row in rows
        ]

        return EventSummaryResponse(
            items=items,
            total=len(items),
            offset=0,
            limit=len(items),
        )

    async def get_event_trend(
        self,
        params: EventQueryParams,
        unit: str = "hour",
    ) -> EventTrendResponse:
        """Get event trend (time-series) data."""
        # Determine time format based on unit
        time_format = {
            "hour": "%Y-%m-%d %H:00",
            "day": "%Y-%m-%d",
            "month": "%Y-%m",
            "year": "%Y",
        }.get(unit, "%Y-%m-%d %H:00")

        # Build query with time grouping
        query = select(Event)

        filters = []
        if params.video_id:
            filters.append(Event.video_id == params.video_id)
        if params.object_type:
            filters.append(Event.object_type == params.object_type)
        if params.start_time > 0:
            filters.append(Event.timestamp >= params.start_time)
        if params.end_time > 0:
            filters.append(Event.timestamp <= params.end_time)

        if filters:
            query = query.where(and_(*filters))

        result = await self.db.execute(query)
        events = result.scalars().all()

        # Group events by time and type
        trend_data: dict[str, dict[str, int]] = {}
        type_set: set[str] = set()

        for event in events:
            ts = event.timestamp
            # Convert timestamp to datetime
            if ts:
                dt = datetime.fromtimestamp(ts / 1000)
                time_key = dt.strftime(time_format)

                if time_key not in trend_data:
                    trend_data[time_key] = {}

                obj_type = event.object_type or "unknown"
                type_set.add(obj_type)

                if obj_type not in trend_data[time_key]:
                    trend_data[time_key][obj_type] = 0
                trend_data[time_key][obj_type] += 1

        # Sort categories (time keys)
        categories = sorted(trend_data.keys())

        # Build series data
        series: dict[str, list[int]] = {}
        total: list[int] = []

        for cat in categories:
            cat_total = 0
            for obj_type in type_set:
                if obj_type not in series:
                    series[obj_type] = []
                count = trend_data.get(cat, {}).get(obj_type, 0)
                series[obj_type].append(count)
                cat_total += count
            total.append(cat_total)

        return EventTrendResponse(
            categories=categories,
            series=series,
            total=total,
        )

    async def get_event_image(self, event_id: int) -> bytes | None:
        """Get event image by event ID."""
        # Find image metadata
        result = await self.db.execute(
            select(Image).where(Image.event_id == event_id)
        )
        image = result.scalar_one_or_none()

        if not image:
            return None

        # Read image file
        image_path = Path(settings.data_save_folder) / image.path
        if not image_path.exists():
            return None

        return image_path.read_bytes()

    async def get_protocol(self, protocol_type: str = "eventpolling") -> ProtocolDTO | None:
        """Get protocol by type."""
        result = await self.db.execute(
            select(Protocol).where(Protocol.type == protocol_type)
        )
        protocol = result.scalar_one_or_none()
        if not protocol:
            return None
        return ProtocolDTO.model_validate(protocol)

    async def create_or_update_protocol(
        self, protocol_type: str, format_str: str
    ) -> ProtocolDTO:
        """Create or update protocol."""
        result = await self.db.execute(
            select(Protocol).where(Protocol.type == protocol_type)
        )
        protocol = result.scalar_one_or_none()

        if protocol:
            protocol.format = format_str
        else:
            protocol = Protocol(type=protocol_type, format=format_str)
            self.db.add(protocol)

        await self.db.commit()
        await self.db.refresh(protocol)
        return ProtocolDTO.model_validate(protocol)

    async def transform_events_with_protocol(
        self,
        events: list[EventDTO],
        protocol: ProtocolDTO | None,
    ) -> list[dict[str, Any]]:
        """Transform events using protocol format."""
        if not protocol or not protocol.format:
            return [e.model_dump(by_alias=True) for e in events]

        # Parse protocol format (JSON schema)
        try:
            format_schema = json.loads(protocol.format)
        except json.JSONDecodeError:
            return [e.model_dump(by_alias=True) for e in events]

        # Transform each event
        transformed = []
        for event in events:
            event_dict = event.model_dump(by_alias=True)
            transformed_event = self._apply_protocol(event_dict, format_schema)
            transformed.append(transformed_event)

        return transformed

    def _apply_protocol(
        self,
        event: dict[str, Any],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply protocol schema to event."""
        result = {}
        for key, mapping in schema.items():
            if isinstance(mapping, str):
                # Direct field mapping
                result[key] = event.get(mapping)
            elif isinstance(mapping, dict):
                # Nested mapping
                result[key] = self._apply_protocol(event, mapping)
        return result

    def _to_dto(self, event: Event) -> EventDTO:
        """Convert Event model to DTO."""
        objects = event.get_objects()
        return EventDTO(
            id=event.id,
            event_setting_id=event.event_setting_id,
            event_setting_name=event.event_setting_name,
            video_id=event.video_id,
            video_name=event.video_name,
            app_id=event.app_id,
            timestamp=event.normalized_timestamp,
            caption=event.caption,
            desc=event.desc,
            device_id=event.device_id,
            vms_id=event.vms_id,
            objects=[EventObject(**obj) for obj in objects],
            object_type=event.object_type,
        )
