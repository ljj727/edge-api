"""MediaMTX settings model for storing connection configuration."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class MediaMTXSettings(Base):
    """MediaMTX connection settings stored in database."""

    __tablename__ = "mediamtx_settings"

    # Single row - always use id=1
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # Connection URLs
    api_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        default="http://localhost:9997/v3",
    )
    hls_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        default="http://localhost:8888",
    )
    webrtc_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        default="http://localhost:8889",
    )
    rtsp_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        default="rtsp://localhost:8554",
    )

    # Enable/disable MediaMTX integration
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

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
        return f"<MediaMTXSettings(api_url={self.api_url})>"
