"""Authentication schemas."""

from pydantic import BaseModel, Field


class UserLogin(BaseModel):
    """Login request schema."""

    id: str = Field(..., description="User ID")
    password: str = Field(..., description="User password")


class Token(BaseModel):
    """JWT token response schema."""

    token: str = Field(..., description="JWT access token")


class ChangePassword(BaseModel):
    """Change password request schema."""

    password: str = Field(..., min_length=1, description="New password")
