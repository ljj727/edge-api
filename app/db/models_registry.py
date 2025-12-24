"""
Model registry for Alembic migrations.

Import all models here to ensure they are registered with SQLAlchemy metadata.
This file should be imported by alembic/env.py.
"""

from app.db.base import Base
from app.models.camera import Camera
from app.models.event import Event
from app.models.event_setting import EventSetting
from app.models.eventpush import Eventpush
from app.models.image import Image
from app.models.inference import Inference
from app.models.mx import Mx
from app.models.protocol import Protocol
from app.models.registry import Registry
from app.models.subscription import BaseEventSubscription, Subscription
from app.models.user import User
from app.models.video import Video

__all__ = [
    "Base",
    "Camera",
    "Event",
    "EventSetting",
    "Eventpush",
    "Image",
    "Inference",
    "Mx",
    "Protocol",
    "Registry",
    "BaseEventSubscription",
    "Subscription",
    "User",
    "Video",
]
