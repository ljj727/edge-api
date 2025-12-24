"""Mx (ViveEX) schemas for API request/response."""

from pydantic import BaseModel, Field


class MxCreate(BaseModel):
    """Mx creation schema."""

    ip: str = "127.0.0.1"
    name: str = "ViveEX"
    port: str = "7001"
    username: str = "admin"
    password: str


class MxDTO(BaseModel):
    """Mx response schema."""

    id: int
    name: str
    ip: str
    port: str
    username: str
    password: str

    model_config = {"from_attributes": True}


class MxDevices(BaseModel):
    """Mx devices schema."""

    id: str
    uri: str
    name: str
    status: str = "Offline"
    server_id: str | None = Field(None, alias="serverId")

    model_config = {"populate_by_name": True}


class MxSession(BaseModel):
    """Mx session response schema."""

    age_s: int = Field(0, alias="ageS")
    expires_in_s: int = Field(0, alias="expiresInS")
    token: str
    username: str

    model_config = {"populate_by_name": True}


class MxSystemInfo(BaseModel):
    """Mx system info schema."""

    cloud_host: str | None = Field(None, alias="cloudHost")
    customization: str | None = None
    devices: list[str] = []
    local_id: str | None = Field(None, alias="localId")
    name: str | None = None
    proto_version: str | None = Field(None, alias="protoVersion")
    servers: list[str] = []
    synchronized_time_ms: int | None = Field(None, alias="synchronizedTimeMs")
    version: str | None = None

    model_config = {"populate_by_name": True}
