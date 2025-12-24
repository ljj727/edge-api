"""Subscription models for event subscriptions."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Subscription(Base):
    """Subscription database model."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(255))


class BaseEventSubscription(Base):
    """Base event subscription - composite key (event_name, subscription_id)."""

    __tablename__ = "base_event_subscriptions"

    event_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    subscription_id: Mapped[int] = mapped_column(Integer, primary_key=True)
