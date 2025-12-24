"""Mx service for ViveEX integration."""

import base64
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mx import Mx
from app.schemas.mx import MxCreate, MxDTO, MxDevices
from app.services.base_service import BaseService


class MxService(BaseService[Mx]):
    """Mx (ViveEX) service for VMS integration."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Mx)

    async def get_all_dto(self) -> list[MxDTO]:
        """Get all Mx configurations as DTOs."""
        items = await self.get_all()
        return [MxDTO.model_validate(m) for m in items]

    async def create_mx(self, data: MxCreate) -> MxDTO:
        """Create new Mx configuration."""
        mx = Mx(
            name=data.name,
            ip=data.ip,
            port=data.port,
            username=data.username,
            password=data.password,
        )
        mx = await self.create(mx)
        return MxDTO.model_validate(mx)

    async def update_mx(
        self, mx_id: int, data: MxCreate
    ) -> MxDTO | None:
        """Update Mx configuration."""
        mx = await self.get_by_id(mx_id)
        if not mx:
            return None

        mx.name = data.name
        mx.ip = data.ip
        mx.port = data.port
        mx.username = data.username
        mx.password = data.password

        await self.update(mx)
        return MxDTO.model_validate(mx)

    async def delete_mx(self, mx_id: int) -> bool:
        """Delete Mx configuration."""
        mx = await self.get_by_id(mx_id)
        if not mx:
            return False

        await self.delete(mx)
        return True

    async def get_devices(self, mx_id: int) -> list[MxDevices]:
        """Get devices from ViveEX."""
        mx = await self.get_by_id(mx_id)
        if not mx:
            return []

        # Create session with ViveEX
        session = await self._create_session(mx)
        if not session:
            return []

        # Get devices
        base_url = f"https://{mx.ip}:{mx.port}"
        headers = {"Authorization": f"Bearer {session['token']}"}

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            try:
                # Get system info
                response = await client.get(
                    f"{base_url}/rest/v2/systems/this",
                    headers=headers,
                )
                if response.status_code != 200:
                    return []

                system_info = response.json()
                device_ids = system_info.get("devices", [])

                # Get each device info
                devices = []
                for device_id in device_ids:
                    device_response = await client.get(
                        f"{base_url}/rest/v2/devices/{device_id}",
                        headers=headers,
                    )
                    if device_response.status_code == 200:
                        device_data = device_response.json()
                        devices.append(
                            MxDevices(
                                id=device_data.get("id", device_id),
                                uri=device_data.get("url", ""),
                                name=device_data.get("name", ""),
                                status=device_data.get("status", "Offline"),
                                server_id=device_data.get("serverId"),
                            )
                        )

                return devices

            except httpx.RequestError:
                return []

    async def _create_session(self, mx: Mx) -> dict[str, Any] | None:
        """Create ViveEX session."""
        base_url = f"https://{mx.ip}:{mx.port}"

        # Base64 encode credentials
        credentials = f"{mx.username}:{mx.password}"
        auth_header = base64.b64encode(credentials.encode()).decode()

        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{base_url}/rest/v2/login/sessions",
                    headers={"Authorization": f"Basic {auth_header}"},
                )
                if response.status_code == 200:
                    return response.json()
                return None
            except httpx.RequestError:
                return None
