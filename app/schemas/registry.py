"""Registry schemas for API request/response."""

from pydantic import BaseModel, Field


class RegistryCreate(BaseModel):
    """Registry creation schema."""

    ip: str
    port: str
    user_id: str = Field(..., alias="userId")
    user_pw: str = Field(..., alias="userPw")

    model_config = {"populate_by_name": True}


class RegistryDTO(BaseModel):
    """Registry response schema."""

    id: int
    ip: str
    port: str
    user_id: str = Field(..., alias="userId")
    user_pw: str = Field(..., alias="userPw")

    model_config = {"populate_by_name": True, "from_attributes": True}


class RegistryAppDTO(BaseModel):
    """Registry app response schema."""

    server_id: str | None = Field(None, alias="serverId")
    id: str | None = None
    app_id: str | None = Field(None, alias="appId")
    location: str | None = None
    name: str | None = None
    version: str | None = None
    description: str | None = None

    model_config = {"populate_by_name": True}
