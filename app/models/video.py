"""Video model for stream configuration."""

import json
from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Video(Base):
    """Video/Stream database model."""

    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    uri: Mapped[str] = mapped_column(String(1024))
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    server_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Settings stored as JSON
    settings: Mapped[str | None] = mapped_column(Text, nullable=True)

    def get_settings(self) -> dict[str, Any]:
        """Deserialize settings JSON."""
        if not self.settings:
            return {
                "masking_region": [],
                "detection_point": "c:b",
                "line_cross_point": "c:c",
            }
        try:
            return json.loads(self.settings)
        except json.JSONDecodeError:
            return {}

    def set_settings(self, settings: dict[str, Any]) -> None:
        """Serialize settings to JSON."""
        self.settings = json.dumps(settings) if settings else None
