"""Mx model for ViveEX connection configuration."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Mx(Base):
    """Mx (ViveEX) database model."""

    __tablename__ = "mx"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), default="ViveEX")
    ip: Mapped[str] = mapped_column(String(255), default="127.0.0.1")
    port: Mapped[str] = mapped_column(String(10), default="7001")
    username: Mapped[str] = mapped_column(String(255), default="admin")
    password: Mapped[str] = mapped_column(String(255))
