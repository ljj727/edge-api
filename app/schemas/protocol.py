"""Protocol schemas for API request/response."""

from pydantic import BaseModel


class ProtocolDTO(BaseModel):
    """Protocol response schema."""

    id: int
    type: str
    format: str | None = None

    model_config = {"from_attributes": True}


class ProtocolCreate(BaseModel):
    """Protocol creation schema."""

    type: str
    format: str
