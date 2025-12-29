"""NATS publisher for sending messages to Core (event-compositor)."""

import json
from dataclasses import dataclass
from typing import Any

import nats
from loguru import logger
from nats.aio.client import Client as NatsClient

from app.core.config import get_settings

settings = get_settings()

# NATS request timeout in seconds
NATS_REQUEST_TIMEOUT = 10.0


@dataclass
class EventSettingResponse:
    """Response from event-compositor for event setting update.

    Matches Rust ConfigResultMSG structure:
    - status: 0 = fail, 1 = success
    - result: "Success" or error message
    - term_ev_list: list of terminal event IDs to watch for events
    """

    status: int
    message: str
    term_ev_list: list[str]

    @property
    def success(self) -> bool:
        """Check if the update was successful."""
        return self.status == 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventSettingResponse":
        """Create from dict (NATS response)."""
        return cls(
            status=data.get("status", 0),
            message=data.get("result", data.get("message", "")),
            term_ev_list=data.get("term_ev_list", []),
        )

    @classmethod
    def error(cls, message: str) -> "EventSettingResponse":
        """Create an error response."""
        return cls(status=0, message=message, term_ev_list=[])


class NatsPublisher:
    """NATS publisher for sending messages to Core (event-compositor).

    Subject format for event settings:
    - Update: stream_id.{video_id}.app_id.{app_id}.update

    Request-response pattern:
    - Send InferenceSettings → Receive ConfigResultMSG
    """

    _instance: "NatsPublisher | None" = None
    _client: NatsClient | None = None

    def __new__(cls) -> "NatsPublisher":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        """Connect to NATS server."""
        if self._client and self._client.is_connected:
            return

        try:
            self._client = await nats.connect(settings.nats_uri)
            logger.info(f"NATS Publisher connected to {settings.nats_uri}")
        except Exception as e:
            logger.error(f"Failed to connect NATS Publisher: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("NATS Publisher disconnected")

    async def _ensure_connected(self) -> bool:
        """Ensure NATS is connected."""
        if not self._client or not self._client.is_connected:
            logger.warning("NATS Publisher not connected, attempting to connect...")
            try:
                await self.connect()
                return True
            except Exception:
                return False
        return True

    async def publish(self, subject: str, data: dict[str, Any]) -> bool:
        """Publish message to NATS subject (fire-and-forget)."""
        if not await self._ensure_connected():
            return False

        try:
            payload = json.dumps(data).encode()
            await self._client.publish(subject, payload)
            logger.debug(f"Published to {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish to {subject}: {e}")
            return False

    async def request(
        self, subject: str, data: dict[str, Any], timeout: float = NATS_REQUEST_TIMEOUT
    ) -> dict[str, Any] | None:
        """Send request and wait for response."""
        if not await self._ensure_connected():
            return None

        try:
            payload = json.dumps(data).encode()
            response = await self._client.request(subject, payload, timeout=timeout)
            result = json.loads(response.data.decode())
            logger.debug(f"Request to {subject} got response: {result}")
            return result
        except nats.errors.TimeoutError:
            logger.warning(f"Request to {subject} timed out after {timeout}s")
            return None
        except Exception as e:
            logger.error(f"Failed to request {subject}: {e}")
            return None

    async def publish_event_setting_update(
        self,
        app_id: str,
        video_id: str,
        settings: dict[str, Any],
    ) -> EventSettingResponse:
        """Send event setting update to Core (event-compositor).

        Subject format: stream_id.{video_id}.app_id.{app_id}.update
        This matches the legacy C# format and what Rust compositor expects.

        Args:
            app_id: Application ID
            video_id: Video/Stream ID
            settings: InferenceSettings dict with version and configs

        Returns:
            EventSettingResponse with status, message, and terminal event list
        """
        # Subject format matches legacy: stream_id.{videoId}.app_id.{appId}.update
        subject = f"stream_id.{video_id}.app_id.{app_id}.update"

        logger.info(f"Sending event setting update to {subject}")
        logger.debug(f"Settings payload: {settings}")

        response = await self.request(subject, settings)

        if response is None:
            return EventSettingResponse.error("NATS request failed or timed out")

        result = EventSettingResponse.from_dict(response)

        if result.success:
            logger.info(
                f"Event setting update successful for {app_id}/{video_id}, "
                f"terminal events: {result.term_ev_list}"
            )
        else:
            logger.warning(
                f"Event setting update failed for {app_id}/{video_id}: {result.message}"
            )

        return result

    async def publish_simple_event_setting_update(
        self,
        app_id: str,
        video_id: str,
        settings: dict[str, Any],
    ) -> bool:
        """Simple fire-and-forget event setting update.

        Use this when you don't need the response (e.g., background sync).
        """
        subject = f"stream_id.{video_id}.app_id.{app_id}.update"
        return await self.publish(subject, settings)


# Global instance
_publisher: NatsPublisher | None = None


async def get_nats_publisher() -> NatsPublisher:
    """Get NATS publisher singleton instance."""
    global _publisher
    if _publisher is None:
        _publisher = NatsPublisher()
    return _publisher
