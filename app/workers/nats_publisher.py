"""NATS publisher for sending messages to Core."""

import json
from typing import Any

import nats
from loguru import logger
from nats.aio.client import Client as NatsClient

from app.core.config import get_settings

settings = get_settings()


class NatsPublisher:
    """NATS publisher for sending messages to Core."""

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

    async def publish(self, subject: str, data: dict[str, Any]) -> bool:
        """Publish message to NATS subject."""
        if not self._client or not self._client.is_connected:
            logger.warning("NATS Publisher not connected, attempting to connect...")
            try:
                await self.connect()
            except Exception:
                return False

        try:
            payload = json.dumps(data).encode()
            await self._client.publish(subject, payload)
            logger.debug(f"Published to {subject}: {data}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish to {subject}: {e}")
            return False

    async def publish_event_setting_update(
        self,
        app_id: str,
        video_id: str,
        settings: dict[str, Any],
    ) -> bool:
        """Publish event setting update to Core.

        Subject format: event.setting.update.{app_id}.{video_id}
        """
        subject = f"event.setting.update.{app_id}.{video_id}"
        data = {
            "type": "event_setting_update",
            "app_id": app_id,
            "video_id": video_id,
            "settings": settings,
        }
        return await self.publish(subject, data)


# Global instance
_publisher: NatsPublisher | None = None


async def get_nats_publisher() -> NatsPublisher:
    """Get NATS publisher singleton instance."""
    global _publisher
    if _publisher is None:
        _publisher = NatsPublisher()
    return _publisher
