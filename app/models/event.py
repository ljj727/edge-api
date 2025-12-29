"""Event model for storing detection events."""

import json
from typing import Any

from sqlalchemy import BigInteger, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Event(Base):
    """Event database model - stores detection events from the inference engine."""

    __tablename__ = "events"

    # SQLite requires INTEGER (not BIGINT) for autoincrement
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Event identification
    event_setting_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_setting_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Video/Stream reference
    video_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    video_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    app_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Event metadata
    timestamp: Mapped[int] = mapped_column(BigInteger, index=True)  # Unix timestamp in ms
    caption: Mapped[str | None] = mapped_column(String(512), nullable=True)
    desc: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Device reference
    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vms_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Detection objects (stored as JSON string)
    objects: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Denormalized field for performance (first object label)
    object_type: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Indexes for common queries
    __table_args__ = (
        Index("ix_events_timestamp_video_id", "timestamp", "video_id"),
        Index("ix_events_timestamp_object_type", "timestamp", "object_type"),
        Index("ix_events_summary", "video_id", "object_type", "timestamp"),
    )

    def get_objects(self) -> list[dict[str, Any]]:
        """Deserialize objects JSON to list."""
        if not self.objects:
            return []
        try:
            return json.loads(self.objects)
        except json.JSONDecodeError:
            return []

    def set_objects(self, objects: list[dict[str, Any]]) -> None:
        """Serialize objects list to JSON and set object_type."""
        self.objects = json.dumps(objects) if objects else None
        # Denormalize first object label for performance
        if objects and len(objects) > 0:
            self.object_type = objects[0].get("label")
        else:
            self.object_type = None

    @property
    def normalized_timestamp(self) -> int:
        """Normalize timestamp to 13-digit milliseconds."""
        if self.timestamp is None:
            return 0

        ts_str = str(self.timestamp)
        if len(ts_str) == 10:  # seconds
            return self.timestamp * 1000
        elif len(ts_str) == 16:  # microseconds
            return self.timestamp // 1000
        return self.timestamp  # already milliseconds
