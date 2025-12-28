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


class ServiceHealth(BaseModel):
    """Individual service health status."""

    status: str  # "connected", "disconnected", "error"
    latency_ms: float | None = Field(None, alias="latencyMs")
    message: str | None = None
    details: dict | None = None

    model_config = {"populate_by_name": True}


class SystemHealthResponse(BaseModel):
    """System health check response."""

    healthy: bool
    core: ServiceHealth
    mediamtx: ServiceHealth
    nats: ServiceHealth
    database: ServiceHealth

    model_config = {"populate_by_name": True}


class SystemStatusResponse(BaseModel):
    """System status summary response."""

    apps_count: int = Field(..., alias="appsCount")
    cameras_count: int = Field(..., alias="camerasCount")
    active_inferences: int = Field(..., alias="activeInferences")
    total_events: int = Field(..., alias="totalEvents")
    pending_eventpushes: int = Field(..., alias="pendingEventpushes")
    disk_usage_percent: float = Field(..., alias="diskUsagePercent")
    uptime_seconds: int | None = Field(None, alias="uptimeSeconds")

    model_config = {"populate_by_name": True}


class SyncResult(BaseModel):
    """Individual sync result."""

    name: str
    success: bool
    added: int = 0
    updated: int = 0
    deleted: int = 0
    message: str | None = None


class SyncAllResponse(BaseModel):
    """Sync all response."""

    success: bool
    message: str
    results: list[SyncResult]


class CleanupResponse(BaseModel):
    """Cleanup response."""

    success: bool
    message: str
    events_deleted: int = Field(0, alias="eventsDeleted")
    images_deleted: int = Field(0, alias="imagesDeleted")
    disk_freed_mb: float = Field(0, alias="diskFreedMb")

    model_config = {"populate_by_name": True}
