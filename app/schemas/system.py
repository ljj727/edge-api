"""System schemas for API request/response."""

from pydantic import BaseModel, Field


class SystemInfo(BaseModel):
    """System info response schema."""

    id: str | None = None
    name: str | None = None
    address: str | None = None
    dx_id: str | None = Field(None, alias="dxId")
    license_type: str | None = Field(None, alias="licenseType")
    end_date: str | None = Field(None, alias="endDate")
    license_key: str | None = Field(None, alias="licenseKey")
    version: str | None = None
    framework: str | None = None
    capacity: int | None = None
    activated: bool = False
    nats_port: int = Field(4422, alias="natsPort")
    launcher_port: int = Field(8500, alias="launcherPort")

    model_config = {"populate_by_name": True}


class LicenseDownload(BaseModel):
    """License download request schema."""

    license_key: str = Field(..., alias="licenseKey")
    state: str | None = None

    model_config = {"populate_by_name": True}


class MetricsResponse(BaseModel):
    """System metrics response schema."""

    cpu_percent: float = Field(..., alias="cpuPercent")
    memory_total: int = Field(..., alias="memoryTotal")
    memory_used: int = Field(..., alias="memoryUsed")
    memory_percent: float = Field(..., alias="memoryPercent")
    disk_total: int = Field(..., alias="diskTotal")
    disk_used: int = Field(..., alias="diskUsed")
    disk_percent: float = Field(..., alias="diskPercent")

    model_config = {"populate_by_name": True}


class SensorTypeProtocol(BaseModel):
    """Sensor type protocol schema."""

    alarm_type: str = Field(..., alias="alarmType")
    alarm_value: list[str] = Field(default_factory=list, alias="alarmValue")
    duration: int | None = None

    model_config = {"populate_by_name": True}


class SensorType(BaseModel):
    """Sensor type schema."""

    id: str
    name: str
    protocol: list[SensorTypeProtocol] = []


class Sensor(BaseModel):
    """Sensor schema."""

    id: str
    name: str
    type_id: str = Field(..., alias="typeId")
    ip: str | None = None
    port: int | None = None

    model_config = {"populate_by_name": True}
