"""Security utilities for authentication and authorization."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    # Support test hash format with $plain$ prefix
    if hashed_password.startswith("$plain$"):
        expected_hash = hashed_password[7:]  # Remove $plain$ prefix
        actual_hash = hashlib.sha256(plain_password.encode()).hexdigest()
        return expected_hash == actual_hash

    # bcrypt has a 72 byte limit, truncate if needed
    truncated = plain_password[:72].encode("utf-8")
    return bcrypt.checkpw(truncated, hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    # bcrypt has a 72 byte limit, truncate if needed
    truncated = password[:72].encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(truncated, salt).decode("utf-8")


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )

    to_encode.update({
        "exp": expire,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    })

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
        return payload
    except JWTError:
        return None


def get_token_data(token: str) -> dict[str, Any] | None:
    """Extract data from JWT token without full validation."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False, "verify_aud": False, "verify_iss": False},
        )
        return payload
    except JWTError:
        return None
