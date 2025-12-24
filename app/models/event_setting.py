"""EventSetting model for event detection configuration."""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EventSetting(Base):
    """Event setting database model."""

    __tablename__ = "event_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(255))
    config: Mapped[str | None] = mapped_column(Text, nullable=True)
