"""Image model for event image metadata."""

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Image(Base):
    """Image database model."""

    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(BigInteger, index=True)
    path: Mapped[str] = mapped_column(String(1024))
    timestamp: Mapped[int] = mapped_column(BigInteger, index=True)
