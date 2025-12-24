"""Registry model for app registry server configuration."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Registry(Base):
    """Registry database model."""

    __tablename__ = "registries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ip: Mapped[str] = mapped_column(String(255))
    port: Mapped[str] = mapped_column(String(10))
    user_id: Mapped[str] = mapped_column(String(255))
    user_pw: Mapped[str] = mapped_column(String(255))
    token: Mapped[str | None] = mapped_column(String(1024), nullable=True)
