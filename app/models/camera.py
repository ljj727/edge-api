"""Camera model for IP camera management."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class Camera(Base):
    """Camera database model - stores IP camera configurations for streaming."""

    __tablename__ = "cameras"

    # Primary key - user-defined camera ID (e.g., "cam1", "front-door")
    id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Camera display name
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # RTSP URL for the camera stream
    rtsp_url: Mapped[str] = mapped_column(String(1024), nullable=False)

    # Optional description
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Camera location (optional metadata)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Camera manufacturer/model info (optional)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Stream status tracking
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        onupdate=func.now(),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<Camera(id={self.id}, name={self.name})>"
