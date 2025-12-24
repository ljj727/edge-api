"""Base service class with common database operations."""

from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseService(Generic[ModelType]):
    """Base service with common CRUD operations."""

    def __init__(self, db: AsyncSession, model: type[ModelType]):
        self.db = db
        self.model = model

    async def get_by_id(self, id: Any) -> ModelType | None:
        """Get entity by primary key."""
        return await self.db.get(self.model, id)

    async def get_all(self) -> list[ModelType]:
        """Get all entities."""
        result = await self.db.execute(select(self.model))
        return list(result.scalars().all())

    async def create(self, obj: ModelType) -> ModelType:
        """Create new entity."""
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj: ModelType) -> ModelType:
        """Update existing entity."""
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj: ModelType) -> None:
        """Delete entity."""
        await self.db.delete(obj)
        await self.db.commit()

    async def delete_by_id(self, id: Any) -> bool:
        """Delete entity by primary key."""
        obj = await self.get_by_id(id)
        if obj:
            await self.delete(obj)
            return True
        return False
