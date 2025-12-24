"""Auth service for authentication."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.schemas.auth import Token
from app.services.user_service import UserService


class AuthService:
    """Authentication service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)

    async def login(self, user_id: str, password: str) -> Token | None:
        """Authenticate user and return JWT token."""
        user = await self.user_service.authenticate(user_id, password)
        if not user:
            return None

        token = create_access_token(
            data={
                "sub": user.id,
                "username": user.username,
            }
        )
        return Token(token=token)
