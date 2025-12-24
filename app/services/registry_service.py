"""Registry service for app registry management."""

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registry import Registry
from app.schemas.registry import RegistryAppDTO, RegistryCreate, RegistryDTO
from app.services.base_service import BaseService


class RegistryService(BaseService[Registry]):
    """Registry service for app registry operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Registry)

    async def get_all_dto(self) -> list[RegistryDTO]:
        """Get all registries as DTOs."""
        items = await self.get_all()
        return [
            RegistryDTO(
                id=r.id,
                ip=r.ip,
                port=r.port,
                user_id=r.user_id,
                user_pw=r.user_pw,
            )
            for r in items
        ]

    async def create_registry(self, data: RegistryCreate) -> RegistryDTO:
        """Create new registry configuration."""
        # Authenticate with registry
        token = await self._authenticate(
            ip=data.ip,
            port=data.port,
            user_id=data.user_id,
            user_pw=data.user_pw,
        )

        registry = Registry(
            ip=data.ip,
            port=data.port,
            user_id=data.user_id,
            user_pw=data.user_pw,
            token=token,
        )
        registry = await self.create(registry)

        return RegistryDTO(
            id=registry.id,
            ip=registry.ip,
            port=registry.port,
            user_id=registry.user_id,
            user_pw=registry.user_pw,
        )

    async def is_connected(self, registry_id: int) -> bool:
        """Check if registry is connected."""
        registry = await self.get_by_id(registry_id)
        if not registry:
            return False

        # Try to refresh token
        token = await self._authenticate(
            ip=registry.ip,
            port=registry.port,
            user_id=registry.user_id,
            user_pw=registry.user_pw,
        )

        if token:
            registry.token = token
            await self.update(registry)
            return True
        return False

    async def get_apps(self, registry_id: int) -> list[RegistryAppDTO]:
        """Get apps from registry."""
        registry = await self.get_by_id(registry_id)
        if not registry or not registry.token:
            return []

        base_url = f"http://{registry.ip}:{registry.port}"
        headers = {"Authorization": f"Bearer {registry.token}"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{base_url}/api/v1/apps",
                    headers=headers,
                )
                if response.status_code != 200:
                    return []

                apps_data = response.json()
                return [
                    RegistryAppDTO(
                        server_id=app.get("serverId"),
                        id=app.get("id"),
                        app_id=app.get("appId"),
                        location=app.get("location"),
                        name=app.get("name"),
                        version=app.get("version"),
                        description=app.get("description"),
                    )
                    for app in apps_data
                ]
            except httpx.RequestError:
                return []

    async def get_app_cover_image(
        self, registry_id: int, app_id: str
    ) -> bytes | None:
        """Get app cover image from registry."""
        registry = await self.get_by_id(registry_id)
        if not registry or not registry.token:
            return None

        base_url = f"http://{registry.ip}:{registry.port}"
        headers = {"Authorization": f"Bearer {registry.token}"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{base_url}/api/v1/apps/{app_id}/cover",
                    headers=headers,
                )
                if response.status_code == 200:
                    return response.content
                return None
            except httpx.RequestError:
                return None

    async def download_app(
        self, registry_id: int, app_id: str
    ) -> bytes | None:
        """Download app package from registry."""
        registry = await self.get_by_id(registry_id)
        if not registry or not registry.token:
            return None

        base_url = f"http://{registry.ip}:{registry.port}"
        headers = {"Authorization": f"Bearer {registry.token}"}

        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                response = await client.get(
                    f"{base_url}/api/v1/apps/{app_id}/download",
                    headers=headers,
                )
                if response.status_code == 200:
                    return response.content
                return None
            except httpx.RequestError:
                return None

    async def _authenticate(
        self,
        ip: str,
        port: str,
        user_id: str,
        user_pw: str,
    ) -> str | None:
        """Authenticate with registry and get token."""
        base_url = f"http://{ip}:{port}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{base_url}/api/v1/auth/login",
                    json={"id": user_id, "password": user_pw},
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("token")
                return None
            except httpx.RequestError:
                return None
