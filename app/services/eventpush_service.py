"""Eventpush service for webhook management."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eventpush import Eventpush
from app.models.protocol import Protocol
from app.schemas.eventpush import EventpushCreate, EventpushDTO
from app.schemas.protocol import ProtocolDTO
from app.services.base_service import BaseService


class EventpushService(BaseService[Eventpush]):
    """Eventpush (webhook) service."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Eventpush)

    async def get_all_dto(self) -> list[EventpushDTO]:
        """Get all eventpushes as DTOs."""
        items = await self.get_all()
        return [self._to_dto(e) for e in items]

    async def create_eventpush(self, data: EventpushCreate) -> EventpushDTO:
        """Create new eventpush webhook."""
        eventpush = Eventpush(
            id=str(uuid.uuid4()),
            name=data.name,
            url=data.url,
            enabled=data.enabled,
        )
        eventpush.set_events(data.events)
        eventpush = await self.create(eventpush)
        return self._to_dto(eventpush)

    async def update_events(
        self, eventpush_id: str, events: list[str]
    ) -> EventpushDTO | None:
        """Update eventpush events list."""
        eventpush = await self.get_by_id(eventpush_id)
        if not eventpush:
            return None

        eventpush.set_events(events)
        await self.update(eventpush)
        return self._to_dto(eventpush)

    async def update_state(
        self, eventpush_id: str, enabled: bool
    ) -> EventpushDTO | None:
        """Update eventpush enabled state."""
        eventpush = await self.get_by_id(eventpush_id)
        if not eventpush:
            return None

        eventpush.enabled = enabled
        await self.update(eventpush)
        return self._to_dto(eventpush)

    async def get_protocol(self) -> ProtocolDTO | None:
        """Get eventhook protocol."""
        result = await self.db.execute(
            select(Protocol).where(Protocol.type == "eventhook")
        )
        protocol = result.scalar_one_or_none()
        if not protocol:
            return None
        return ProtocolDTO.model_validate(protocol)

    async def create_or_update_protocol(self, format_str: str) -> ProtocolDTO:
        """Create or update eventhook protocol."""
        result = await self.db.execute(
            select(Protocol).where(Protocol.type == "eventhook")
        )
        protocol = result.scalar_one_or_none()

        if protocol:
            protocol.format = format_str
        else:
            protocol = Protocol(type="eventhook", format=format_str)
            self.db.add(protocol)

        await self.db.commit()
        await self.db.refresh(protocol)
        return ProtocolDTO.model_validate(protocol)

    def _to_dto(self, eventpush: Eventpush) -> EventpushDTO:
        """Convert Eventpush model to DTO."""
        return EventpushDTO(
            id=eventpush.id,
            name=eventpush.name,
            url=eventpush.url,
            events=eventpush.get_events(),
            enabled=eventpush.enabled,
        )
