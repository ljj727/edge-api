"""Stream service for MediaMTX integration."""

from typing import Any

import httpx
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class StreamService:
    """
    Service for managing camera streams via MediaMTX.

    MediaMTX is a media server that converts RTSP streams to HLS/WebRTC
    for browser playback.
    """

    def __init__(self):
        self.api_url = settings.mediamtx_api_url
        self.hls_url = settings.mediamtx_hls_url
        self.webrtc_url = settings.mediamtx_webrtc_url
        self.enabled = settings.mediamtx_enabled
        self._timeout = 10.0

    async def register_camera(self, camera_id: str, rtsp_url: str) -> bool:
        """
        Register a camera stream with MediaMTX.

        Args:
            camera_id: Unique camera identifier (used as path name)
            rtsp_url: RTSP URL of the camera stream

        Returns:
            True if registration succeeded, False otherwise
        """
        if not self.enabled:
            logger.warning("MediaMTX is disabled, skipping camera registration")
            return True

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.api_url}/config/paths/add/{camera_id}",
                    json={"source": rtsp_url},
                    timeout=self._timeout,
                )

                if response.status_code == 200:
                    logger.info(f"Camera {camera_id} registered with MediaMTX")
                    return True

                # Path might already exist, try to patch instead
                if response.status_code == 400:
                    patch_response = await client.patch(
                        f"{self.api_url}/config/paths/patch/{camera_id}",
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
        if not self.enabled:
            logger.warning("MediaMTX is disabled, skipping camera unregistration")
            return True

        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.api_url}/config/paths/delete/{camera_id}",
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
        if not self.enabled:
            logger.warning("MediaMTX is disabled, skipping camera update")
            return True

        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(
                    f"{self.api_url}/config/paths/patch/{camera_id}",
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
        if not self.enabled:
            return {"status": "disabled", "message": "MediaMTX is disabled"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.api_url}/paths/get/{camera_id}",
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
        if not self.enabled:
            return []

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.api_url}/paths/list",
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
        """
        Generate HLS streaming URL for a camera.

        Args:
            camera_id: Camera identifier (MediaMTX path name)

        Returns:
            HLS M3U8 playlist URL
        """
        return f"{self.hls_url}/{camera_id}/index.m3u8"

    def get_webrtc_url(self, camera_id: str) -> str:
        """
        Generate WebRTC WHEP URL for a camera.

        Args:
            camera_id: Camera identifier (MediaMTX path name)

        Returns:
            WebRTC WHEP endpoint URL
        """
        return f"{self.webrtc_url}/{camera_id}/whep"

    async def health_check(self) -> dict[str, Any]:
        """
        Check MediaMTX server health.

        Returns:
            Health status dictionary
        """
        if not self.enabled:
            return {"healthy": True, "message": "MediaMTX is disabled"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.api_url}/paths/list",
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
