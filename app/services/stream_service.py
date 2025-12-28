"""Stream service for MediaMTX integration."""

from typing import Any

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

env_settings = get_settings()


class StreamService:
    """
    Service for managing camera streams via MediaMTX.

    MediaMTX is a media server that converts RTSP streams to HLS/WebRTC
    for browser playback.

    Settings are loaded from DB if available, otherwise from .env defaults.
    """

    def __init__(self):
        # Default settings from .env
        self._api_url = env_settings.mediamtx_api_url
        self._hls_url = env_settings.mediamtx_hls_url
        self._webrtc_url = env_settings.mediamtx_webrtc_url
        self._rtsp_url = env_settings.mediamtx_rtsp_url
        self._enabled = env_settings.mediamtx_enabled
        self._timeout = 10.0
        self._settings_loaded = False

    async def _load_settings_from_db(self, db: AsyncSession) -> None:
        """Load settings from database if available."""
        try:
            from app.models.mediamtx_settings import MediaMTXSettings

            result = await db.execute(
                select(MediaMTXSettings).where(MediaMTXSettings.id == 1)
            )
            db_settings = result.scalar_one_or_none()

            if db_settings:
                self._api_url = db_settings.api_url
                self._hls_url = db_settings.hls_url
                self._webrtc_url = db_settings.webrtc_url
                self._rtsp_url = db_settings.rtsp_url
                self._enabled = db_settings.enabled
                self._settings_loaded = True
                logger.debug("MediaMTX settings loaded from database")
        except Exception as e:
            logger.warning(f"Failed to load MediaMTX settings from DB, using .env: {e}")

    def update_settings(
        self,
        api_url: str,
        hls_url: str,
        webrtc_url: str,
        rtsp_url: str,
        enabled: bool,
    ) -> None:
        """Update settings in memory (called after DB update)."""
        self._api_url = api_url
        self._hls_url = hls_url
        self._webrtc_url = webrtc_url
        self._rtsp_url = rtsp_url
        self._enabled = enabled
        self._settings_loaded = True
        logger.info("MediaMTX settings updated in stream service")

    @property
    def api_url(self) -> str:
        return self._api_url

    @property
    def hls_url(self) -> str:
        return self._hls_url

    @property
    def webrtc_url(self) -> str:
        return self._webrtc_url

    @property
    def rtsp_url(self) -> str:
        return self._rtsp_url

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def register_camera(self, camera_id: str, rtsp_url: str) -> bool:
        """
        Register a camera stream with MediaMTX.

        Args:
            camera_id: Unique camera identifier (used as path name)
            rtsp_url: RTSP URL of the camera stream

        Returns:
            True if registration succeeded, False otherwise
        """
        if not self._enabled:
            logger.warning("MediaMTX is disabled, skipping camera registration")
            return True

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self._api_url}/config/paths/add/{camera_id}",
                    json={"source": rtsp_url},
                    timeout=self._timeout,
                )

                if response.status_code == 200:
                    logger.info(f"Camera {camera_id} registered with MediaMTX")
                    return True

                # Path might already exist, try to patch instead
                if response.status_code == 400:
                    patch_response = await client.patch(
                        f"{self._api_url}/config/paths/patch/{camera_id}",
                        json={"source": rtsp_url},
                        timeout=self._timeout,
                    )
                    if patch_response.status_code == 200:
                        logger.info(f"Camera {camera_id} updated in MediaMTX")
                        return True

                logger.error(
                    f"Failed to register camera {camera_id}: "
                    f"{response.status_code} - {response.text}"
                )
                return False

            except httpx.RequestError as e:
                logger.error(f"MediaMTX connection error for {camera_id}: {e}")
                return False

    async def unregister_camera(self, camera_id: str) -> bool:
        """
        Remove a camera stream from MediaMTX.

        Args:
            camera_id: Camera identifier to remove

        Returns:
            True if removal succeeded, False otherwise
        """
        if not self._enabled:
            logger.warning("MediaMTX is disabled, skipping camera unregistration")
            return True

        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self._api_url}/config/paths/delete/{camera_id}",
                    timeout=self._timeout,
                )

                if response.status_code == 200:
                    logger.info(f"Camera {camera_id} removed from MediaMTX")
                    return True

                # 404 is acceptable - camera might not have been registered
                if response.status_code == 404:
                    logger.warning(f"Camera {camera_id} not found in MediaMTX")
                    return True

                logger.error(
                    f"Failed to unregister camera {camera_id}: "
                    f"{response.status_code} - {response.text}"
                )
                return False

            except httpx.RequestError as e:
                logger.error(f"MediaMTX connection error for {camera_id}: {e}")
                return False

    async def update_camera(self, camera_id: str, rtsp_url: str) -> bool:
        """
        Update a camera stream URL in MediaMTX.

        Args:
            camera_id: Camera identifier
            rtsp_url: New RTSP URL

        Returns:
            True if update succeeded, False otherwise
        """
        if not self._enabled:
            logger.warning("MediaMTX is disabled, skipping camera update")
            return True

        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(
                    f"{self._api_url}/config/paths/patch/{camera_id}",
                    json={"source": rtsp_url},
                    timeout=self._timeout,
                )

                if response.status_code == 200:
                    logger.info(f"Camera {camera_id} updated in MediaMTX")
                    return True

                # If path doesn't exist, create it
                if response.status_code == 404:
                    return await self.register_camera(camera_id, rtsp_url)

                logger.error(
                    f"Failed to update camera {camera_id}: "
                    f"{response.status_code} - {response.text}"
                )
                return False

            except httpx.RequestError as e:
                logger.error(f"MediaMTX connection error for {camera_id}: {e}")
                return False

    async def get_stream_status(self, camera_id: str) -> dict[str, Any]:
        """
        Get the streaming status of a camera from MediaMTX.

        Args:
            camera_id: Camera identifier

        Returns:
            Status dictionary with stream information
        """
        if not self._enabled:
            return {"status": "disabled", "message": "MediaMTX is disabled"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self._api_url}/paths/get/{camera_id}",
                    timeout=5.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "status": "ok",
                        "is_ready": data.get("ready", False),
                        "source_ready": data.get("sourceReady", False),
                        "readers_count": len(data.get("readers", [])),
                        "source": data.get("source", {}).get("type"),
                    }

                if response.status_code == 404:
                    return {"status": "not_found", "message": "Camera not registered"}

                return {"status": "error", "message": response.text}

            except httpx.RequestError as e:
                return {"status": "error", "message": str(e)}

    async def get_all_paths(self) -> list[dict[str, Any]]:
        """
        Get all registered paths from MediaMTX.

        Returns:
            List of path configurations
        """
        if not self._enabled:
            return []

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self._api_url}/paths/list",
                    timeout=5.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("items", [])

                return []

            except httpx.RequestError as e:
                logger.error(f"Failed to get paths from MediaMTX: {e}")
                return []

    def get_hls_url(self, camera_id: str) -> str:
        """Generate HLS streaming URL for a camera."""
        return f"{self._hls_url}/{camera_id}/index.m3u8"

    def get_webrtc_url(self, camera_id: str) -> str:
        """Generate WebRTC WHEP URL for a camera."""
        return f"{self._webrtc_url}/{camera_id}/whep"

    def get_webrtc_player_url(self, camera_id: str) -> str:
        """Generate WebRTC player URL for a camera (iframe embeddable)."""
        return f"{self._webrtc_url}/{camera_id}"

    def get_rtsp_url(self, camera_id: str) -> str:
        """Generate RTSP URL for a camera."""
        return f"{self._rtsp_url}/{camera_id}"

    async def health_check(self) -> dict[str, Any]:
        """Check MediaMTX server health."""
        if not self._enabled:
            return {"healthy": True, "message": "MediaMTX is disabled"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self._api_url}/paths/list",
                    timeout=5.0,
                )

                return {
                    "healthy": response.status_code == 200,
                    "status_code": response.status_code,
                }

            except httpx.RequestError as e:
                return {"healthy": False, "error": str(e)}


# Singleton instance
stream_service = StreamService()
