"""Pydantic schemas for API request/response validation."""

from app.schemas.auth import ChangePassword, Token, UserLogin
from app.schemas.event import (
    EventCreate,
    EventDTO,
    EventObject,
    EventObjectClassifier,
    EventPagedResponse,
    EventQueryParams,
    EventSummaryItem,
    EventSummaryResponse,
    EventTrendResponse,
)
from app.schemas.eventpush import (
    EventpushCreate,
    EventpushDTO,
    EventpushEventMsg,
    EventpushStateUpdate,
    EventpushUpdate,
)
from app.schemas.inference import (
    InferenceCreate,
    InferenceDTO,
    InferenceEventSettingUpdate,
    InferenceSettings,
    InferenceSettingConfig,
    InferenceStreamStart,
    InferenceWithStatus,
)
from app.schemas.mx import MxCreate, MxDTO, MxDevices
from app.schemas.protocol import ProtocolDTO
from app.schemas.registry import RegistryAppDTO, RegistryCreate, RegistryDTO
from app.schemas.system import LicenseDownload, SystemInfo
from app.schemas.video import VideoCreate, VideoDTO, VideoSettingUpdate, VideoSettings

__all__ = [
    # Auth
    "Token",
    "UserLogin",
    "ChangePassword",
    # Event
    "EventCreate",
    "EventDTO",
    "EventObject",
    "EventObjectClassifier",
    "EventPagedResponse",
    "EventQueryParams",
    "EventSummaryItem",
    "EventSummaryResponse",
    "EventTrendResponse",
    # Eventpush
    "EventpushCreate",
    "EventpushDTO",
    "EventpushEventMsg",
    "EventpushStateUpdate",
    "EventpushUpdate",
    # Inference
    "InferenceCreate",
    "InferenceDTO",
    "InferenceEventSettingUpdate",
    "InferenceSettings",
    "InferenceSettingConfig",
    "InferenceStreamStart",
    "InferenceWithStatus",
    # Mx
    "MxCreate",
    "MxDTO",
    "MxDevices",
    # Protocol
    "ProtocolDTO",
    # Registry
    "RegistryAppDTO",
    "RegistryCreate",
    "RegistryDTO",
    # System
    "LicenseDownload",
    "SystemInfo",
    # Video
    "VideoCreate",
    "VideoDTO",
    "VideoSettingUpdate",
    "VideoSettings",
]
