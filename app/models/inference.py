"""Inference model for inference server configuration."""

import json
from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Inference(Base):
    """Inference database model - composite key (app_id, video_id)."""

    __tablename__ = "inferences"

    app_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    video_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    uri: Mapped[str] = mapped_column(String(1024))
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Settings stored as JSON
    settings: Mapped[str | None] = mapped_column(Text, nullable=True)
    node_settings: Mapped[str | None] = mapped_column(Text, nullable=True)

    def get_settings(self) -> dict[str, Any]:
        """Deserialize settings JSON."""
        if not self.settings:
            return {"version": "1.6.1", "configs": []}
        try:
            return json.loads(self.settings)
        except json.JSONDecodeError:
            return {"version": "1.6.1", "configs": []}

    def set_settings(self, settings: dict[str, Any]) -> None:
        """Serialize settings to JSON."""
        self.settings = json.dumps(settings) if settings else None

    def get_node_settings(self) -> dict[str, Any]:
        """Deserialize node settings JSON."""
        if not self.node_settings:
            return {}
        try:
            return json.loads(self.node_settings)
        except json.JSONDecodeError:
            return {}

    def set_node_settings(self, node_settings: dict[str, Any]) -> None:
        """Serialize node settings to JSON."""
        self.node_settings = json.dumps(node_settings) if node_settings else None
