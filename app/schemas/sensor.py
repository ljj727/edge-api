"""Sensor schemas for API request/response.

Ported from legacy Event Bridge (autocare_event_bridge_2.0).
"""

from pydantic import BaseModel, Field


class SensorTypeBase(BaseModel):
    """Base schema for sensor type."""

    name: str = Field(..., description="Protocol name (e.g., IoLogik_E1211)")
    protocol: str = Field(default="", description="Additional protocol details")


class SensorTypeCreate(SensorTypeBase):
    """Schema for creating a sensor type."""

    id: str | None = Field(None, description="Unique type identifier (auto-generated if not provided)")


class SensorTypeDTO(SensorTypeBase):
    """Sensor type response schema."""

    id: str = Field(..., description="Unique type identifier")

    model_config = {"from_attributes": True}


class SensorBase(BaseModel):
    """Base schema for sensor."""

    name: str = Field(..., description="Human-readable sensor name")
    type_id: str = Field(..., alias="typeId", description="Reference to SensorType")
    ip: str = Field(default="0.0.0.0", description="Device IP address")
    port: int = Field(default=80, description="Device port number")

    # Speaker-specific fields
    max_time: int = Field(
        default=120, alias="maxTime", description="Max alarm duration (seconds)"
    )
    pause_time: int = Field(
        default=2, alias="pauseTime", description="Pause between repeats (seconds)"
    )

    # Time restriction fields
    is_time_restricted: bool = Field(
        default=False, alias="isTimeRestricted", description="Enable time restrictions"
    )
    time_restricted_start: int = Field(
        default=0,
        alias="timeRestrictedStart",
        description="Start time in minutes from midnight",
    )
    time_restricted_end: int = Field(
        default=0,
        alias="timeRestrictedEnd",
        description="End time in minutes from midnight",
    )

    model_config = {"populate_by_name": True}


class SensorCreate(SensorBase):
    """Schema for creating a sensor."""

    id: str | None = Field(None, description="Unique sensor identifier (auto-generated if not provided)")


class SensorUpdate(BaseModel):
    """Schema for updating a sensor."""

    name: str | None = Field(None, description="Human-readable sensor name")
    type_id: str | None = Field(None, alias="typeId", description="Reference to SensorType")
    ip: str | None = Field(None, description="Device IP address")
    port: int | None = Field(None, description="Device port number")
    max_time: int | None = Field(None, alias="maxTime")
    pause_time: int | None = Field(None, alias="pauseTime")
    is_time_restricted: bool | None = Field(None, alias="isTimeRestricted")
    time_restricted_start: int | None = Field(None, alias="timeRestrictedStart")
    time_restricted_end: int | None = Field(None, alias="timeRestrictedEnd")

    model_config = {"populate_by_name": True}


class SensorDTO(SensorBase):
    """Sensor response schema."""

    id: str = Field(..., description="Unique sensor identifier")

    model_config = {"populate_by_name": True, "from_attributes": True}


class AlarmMessage(BaseModel):
    """Alarm message from event-compositor via NATS.

    Matches legacy AlarmMsg structure from C#/Rust.

    Attributes:
        id: Sensor ID to trigger
        type_id: Sensor type ID for module selection
        alarm_type: Type of alarm (e.g., "LED", "BUZZER")
        alarm_value: Alarm value (e.g., "RED", "1", port number)
        duration: Alarm duration in seconds
        regen_interval: Regeneration interval in seconds
        priority: Alarm priority (1-10, lower is higher)
        on_off: On/Off flag (1=On, 0=Off)
    """

    id: str = Field(default="")
    type_id: str = Field(default="", alias="typeId")
    alarm_type: str = Field(default="", alias="alarmType")
    alarm_value: str = Field(default="", alias="alarmValue")
    duration: int = Field(default=1, description="Duration in seconds")
    regen_interval: int = Field(default=0, alias="regenInterval")
    priority: int = Field(default=0)
    on_off: int | None = Field(default=None, alias="onOff")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_dict(cls, data: dict) -> "AlarmMessage":
        """Create AlarmMessage from dictionary."""
        return cls(
            id=data.get("id", "") or "",
            type_id=data.get("typeId", "") or "",
            alarm_type=data.get("alarmType", "") or "",
            alarm_value=str(data.get("alarmValue", "") or ""),
            duration=int(data.get("duration", 1) or 1),
            regen_interval=int(data.get("regenInterval", 0) or 0),
            priority=int(data.get("priority", 0) or 0),
            on_off=data.get("onOff"),
        )

    @classmethod
    def list_from_payload(cls, payload: list | None) -> list["AlarmMessage"]:
        """Parse NATS payload into list of AlarmMessages."""
        if not isinstance(payload, list):
            return []
        return [cls.from_dict(item) for item in payload if isinstance(item, dict)]
