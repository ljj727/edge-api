"""Eventpush model for webhook configuration."""

import json
import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Eventpush(Base):
    """Eventpush (webhook) database model."""

    __tablename__ = "eventpushes"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(1024))
    events: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    def get_events(self) -> list[str]:
        """Deserialize events JSON to list."""
        if not self.events:
            return []
        try:
            return json.loads(self.events)
        except json.JSONDecodeError:
            return []

    def set_events(self, events: list[str]) -> None:
        """Serialize events list to JSON."""
        self.events = json.dumps(events) if events else None
