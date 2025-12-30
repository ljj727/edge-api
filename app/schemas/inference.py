"""Inference schemas for API request/response."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Supported event types from event-compositor."""

    ROI = "ROI"  # Region of Interest - needs points (>=3), target
    LINE = "Line"  # Line crossing - needs exactly 2 points, direction, target
    AND = "And"  # Logical AND - needs inOrder, >=2 children
    OR = "Or"  # Logical OR - needs >=2 children
    SPEED = "Speed"  # Speed detection - exactly 2 Line children with turn
    HEATMAP = "HM"  # Heatmap - regenInterval
    FILTER = "Filter"  # Filter - needs parentId, optional points
    ENTER_EXIT = "EnEx"  # Enter-Exit counting - target required
    ALARM = "Alarm"  # Alarm - ext required


class InferenceSettingConfigTarget(BaseModel):
    """Target configuration for event detection.

    Matches compositor's expected structure:
    - label: single object label to detect (e.g., "person")
    - classType: type of classifier (e.g., "classifier") or null
    - resultLabel: list of classifier results to filter by (e.g., ["red", "blue"]) or null
    """

    label: str = Field(..., alias="label")
    class_type: str | None = Field(None, alias="classType")
    result_label: list[str] | None = Field(None, alias="resultLabel")

    model_config = {"populate_by_name": True}


class InferenceSettingConfig(BaseModel):
    """Individual event setting configuration.

    Matches legacy InferenceSettingConfig and Rust ConfigMSG structure.
    Event type validation rules (from event-compositor):
    - ROI: points required (>=3 vertices), target required
    - Line: exactly 2 points, direction required (A2B/B2A/BOTH), target required, no classType in target
    - And: inOrder required, >=2 child events (referenced by parentId)
    - Or: >=2 child events
    - Speed: exactly 2 Line children, each Line needs turn (0 or 1)
    - HM (Heatmap): regenInterval for regeneration
    - Filter: parentId required, points optional (>=3 if present)
    - EnEx (Enter-Exit): target required
    - Alarm: ext required (alarm configuration string)
    """

    event_type: str | None = Field(None, alias="eventType")
    event_setting_id: str | None = Field(None, alias="eventSettingId")
    event_setting_name: str | None = Field(None, alias="eventSettingName")
    parent_id: str | None = Field(None, alias="parentId")  # Reference to parent event

    # Geometry - polygon points [[x1,y1], [x2,y2], ...]
    points: list[list[float]] | None = Field(default=None, alias="points")

    # Target objects to detect
    target: InferenceSettingConfigTarget | None = None

    # Timing
    timeout: float | None = Field(None, alias="timeout")  # Seconds
    regen_interval: float | None = Field(None, alias="regenInterval")  # For heatmap

    # Logic conditions
    ncond: str | None = Field(None, alias="ncond")  # e.g., ">=2", "==3" for And/Or
    direction: str | None = Field(None, alias="direction")  # A2B, B2A, BOTH for Line
    in_order: bool | None = Field(None, alias="inOrder")  # For And event

    # Speed event specific
    turn: int | None = Field(None, alias="turn")  # 0 or 1 for Speed's Line children

    # Detection point - where to detect object (will be normalized)
    # Input: centerBottom, leftTop, etc.
    # Normalized: c:b, l:t, etc.
    detection_point: str | None = Field(None, alias="detectionPoint")

    # Extension data (for Alarm)
    ext: str | None = Field(None, alias="ext")

    model_config = {"populate_by_name": True}

    def to_nats_dict(self) -> dict[str, Any]:
        """Convert to dict for NATS message (camelCase keys)."""
        result: dict[str, Any] = {}

        if self.event_type:
            result["eventType"] = self.event_type
        if self.event_setting_id:
            result["eventSettingId"] = self.event_setting_id
        if self.event_setting_name:
            result["eventSettingName"] = self.event_setting_name
        if self.parent_id:
            result["parentId"] = self.parent_id
        if self.points:
            result["points"] = self.points
        if self.target:
            result["target"] = {
                "label": self.target.label,
                "classType": self.target.class_type,
                "resultLabel": self.target.result_label,
            }
        if self.timeout is not None:
            result["timeout"] = self.timeout
        if self.regen_interval is not None:
            result["regenInterval"] = self.regen_interval
        if self.ncond:
            result["ncond"] = self.ncond
        if self.direction:
            result["direction"] = self.direction
        if self.in_order is not None:
            result["inOrder"] = self.in_order
        if self.turn is not None:
            result["turn"] = self.turn
        if self.detection_point:
            result["detectionPoint"] = normalize_detection_point(self.detection_point)
        if self.ext:
            result["ext"] = self.ext

        return result


class InferenceSettings(BaseModel):
    """Inference settings containing event configurations.

    Structure:
    - version: API version (default "1.6.1")
    - configs: list of event setting configurations

    The configs form a tree structure via parentId references:
    - Root events: no parentId
    - Child events: reference parent via parentId (e.g., And/Or children, Filter parent)
    """

    version: str = "1.6.1"
    configs: list[InferenceSettingConfig] = Field(default_factory=list)

    def to_nats_dict(self) -> dict[str, Any]:
        """Convert to dict for NATS message."""
        return {
            "version": self.version,
            "configs": [c.to_nats_dict() for c in self.configs],
        }


# Detection point normalization mapping
# Legacy format: "centerBottom" → Normalized: "c:b"
# Format: "x:y" where x = l(left)/c(center)/r(right), y = t(top)/c(center)/b(bottom)
DETECTION_POINT_MAP: dict[str, str] = {
    # Full names
    "leftTop": "l:t",
    "centerTop": "c:t",
    "rightTop": "r:t",
    "leftCenter": "l:c",
    "center": "c:c",
    "rightCenter": "r:c",
    "leftBottom": "l:b",
    "centerBottom": "c:b",
    "rightBottom": "r:b",
    # Already normalized
    "l:t": "l:t",
    "c:t": "c:t",
    "r:t": "r:t",
    "l:c": "l:c",
    "c:c": "c:c",
    "r:c": "r:c",
    "l:b": "l:b",
    "c:b": "c:b",
    "r:b": "r:b",
    # Special
    "ALL": "ALL",
    "all": "ALL",
}


def normalize_detection_point(detection_point: str | None) -> str | None:
    """Normalize detection point to short format.

    Converts human-readable format to compositor format:
    - "centerBottom" → "c:b"
    - "leftTop" → "l:t"
    - Already normalized values pass through
    - Unknown values return None
    """
    if not detection_point:
        return None

    normalized = DETECTION_POINT_MAP.get(detection_point)
    if normalized:
        return normalized

    # Check if it's already in short format (x:y)
    if len(detection_point) == 3 and detection_point[1] == ":":
        return detection_point

    return None


class InferenceCreate(BaseModel):
    """Inference creation schema."""

    app_id: str = Field(..., alias="appId")
    video_id: str = Field(..., alias="videoId")
    uri: str
    name: str | None = None
    type: str | None = None
    settings: InferenceSettings | None = None
    node_settings: dict | None = Field(None, alias="nodeSettings")

    model_config = {"populate_by_name": True}


class InferenceDTO(BaseModel):
    """Inference response schema."""

    app_id: str = Field(..., alias="appId")
    video_id: str = Field(..., alias="videoId")
    uri: str
    name: str | None = None
    type: str | None = None
    settings: InferenceSettings | None = None
    node_settings: dict | None = Field(None, alias="nodeSettings")

    model_config = {"populate_by_name": True, "from_attributes": True}


class InferenceEventSettingUpdate(BaseModel):
    """Inference event setting update schema."""

    settings: InferenceSettings
    node_settings: str | None = Field(None, alias="nodeSettings")  # JSON string of complete flow graph for UI restoration

    model_config = {"populate_by_name": True}


class InferenceWithStatus(BaseModel):
    """Inference with status schema."""

    app_id: str = Field(..., alias="appId")
    video_id: str = Field(..., alias="videoId")
    status: int = 0  # NG=0, READY=1, CONNECTING=2, CONNECTED=3
    count: int = 0  # Event count
    eos: bool = False
    err: bool = False

    model_config = {"populate_by_name": True}


class InferenceStreamStart(BaseModel):
    """Inference stream start response schema."""

    location: str
    ts_start: int
    session_id: str


class InferenceSyncResponse(BaseModel):
    """Schema for inference sync response."""

    success: bool
    message: str
    added_to_db: int = 0  # Core에만 있던 것 → DB 추가
    added_to_core: int = 0  # DB에만 있던 것 → Core 추가
    deleted_from_db: int = 0  # Core에 없는 것 → DB 삭제
    failed: int = 0  # 실패 건수


class EventSettingUpdateResponse(BaseModel):
    """Response for event setting update including NATS status.

    Contains:
    - inference: The updated inference configuration
    - nats_sent: Whether NATS message was sent
    - nats_success: Whether event-compositor accepted the settings
    - nats_message: Success/error message from compositor
    - term_ev_list: List of terminal event IDs to watch for events
    """

    inference: InferenceDTO
    nats_sent: bool = False
    nats_success: bool = False
    nats_message: str = ""
    term_ev_list: list[str] = Field(default_factory=list, alias="termEvList")

    model_config = {"populate_by_name": True}
