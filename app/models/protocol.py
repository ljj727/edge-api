"""Protocol model for event data format configuration."""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Protocol(Base):
    """Protocol database model - defines data format schemas."""

    __tablename__ = "protocols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
