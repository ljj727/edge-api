"""Authentication API endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.core.deps import DBSession
from app.schemas.auth import Token, UserLogin
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("", response_model=Token)
async def login(
    credentials: UserLogin,
    db: DBSession,
) -> Token:
    """
    Login and get JWT access token.

    - **id**: User ID
    - **password**: User password
    """
    auth_service = AuthService(db)
    token = await auth_service.login(credentials.id, credentials.password)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    return token
