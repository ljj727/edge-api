"""User service for user management."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.services.base_service import BaseService


class UserService(BaseService[User]):
    """User service for authentication and management."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, User)

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username."""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def authenticate(self, username: str, password: str) -> User | None:
        """Authenticate user by username and password."""
        user = await self.get_by_username(username)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def change_password(self, user_id: str, new_password: str) -> bool:
        """Change user password."""
        user = await self.get_by_id(user_id)
        if not user:
            return False
        user.hashed_password = get_password_hash(new_password)
        await self.update(user)
        return True

    async def create_user(
        self,
        user_id: str,
        username: str,
        password: str,
        is_superuser: bool = False,
    ) -> User:
        """Create new user."""
        user = User(
            id=user_id,
            username=username,
            hashed_password=get_password_hash(password),
            is_active=True,
            is_superuser=is_superuser,
        )
        return await self.create(user)
