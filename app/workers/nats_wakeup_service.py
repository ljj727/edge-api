"""NATS wakeup service for handling compositor startup requests.

When event-compositor starts, it sends 'inference.start' request.
This service responds by sending all stored inference configurations back.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import nats
from loguru import logger
from nats.aio.client import Client as NatsClient
from nats.aio.msg import Msg
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import async_session_maker
from app.models.inference import Inference

settings = get_settings()


class NatsWakeupService:
    """Background service that handles compositor wakeup requests.

    Uses modern async context manager pattern for clean lifecycle management.

    Usage:
        async with NatsWakeupService() as service:
            await service.wait_until_stopped()
    """

    def __init__(self):
        self._client: NatsClient | None = None
        self._subscription = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the service - connect and subscribe."""
        # Connect to NATS
        self._client = await nats.connect(
            settings.nats_uri,
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,  # Infinite reconnect
        )
        logger.info(f"NatsWakeupService connected to {settings.nats_uri}")

        # Subscribe to inference.start
        self._subscription = await self._client.subscribe(
            "inference.start",
            cb=self._handle_wakeup,
        )
        logger.info("NatsWakeupService subscribed to 'inference.start'")

    async def stop(self) -> None:
        """Stop the service - cleanup resources."""
        self._stop_event.set()

        if self._subscription:
            await self._subscription.unsubscribe()

        if self._client:
            await self._client.drain()
            logger.info("NatsWakeupService disconnected")

    async def wait_until_stopped(self) -> None:
        """Wait until stop() is called."""
        await self._stop_event.wait()

    async def __aenter__(self) -> "NatsWakeupService":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()

    async def _handle_wakeup(self, msg: Msg) -> None:
        """Handle inference.start request from compositor."""
        logger.info("Received inference.start request from compositor")

        try:
            async with async_session_maker() as db:
                result = await db.execute(select(Inference))
                inferences = result.scalars().all()

                logger.info(f"Sending {len(inferences)} inference configs to compositor")

                # Send configs concurrently for speed
                tasks = [
                    self._send_inference_to_compositor(inf)
                    for inf in inferences
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

            # Reply to compositor
            if msg.reply:
                await self._client.publish(msg.reply, b"")
                logger.info("Replied to compositor wakeup request")

        except Exception as e:
            logger.error(f"Error handling wakeup request: {e}")
            if msg.reply:
                try:
                    await self._client.publish(msg.reply, b"")
                except Exception:
                    pass

    async def _send_inference_to_compositor(self, inference: Inference) -> None:
        """Send single inference settings to compositor."""
        try:
            settings_dict = inference.get_settings()
            if not settings_dict or not settings_dict.get("configs"):
                return

            subject = f"stream_id.{inference.video_id}.app_id.{inference.app_id}.update"
            payload = json.dumps(settings_dict).encode()

            response = await self._client.request(subject, payload, timeout=5.0)
            response_data = json.loads(response.data.decode())

            if response_data.get("status") == 1:
                logger.info(f"Synced config: {inference.app_id}/{inference.video_id}")
            else:
                logger.warning(
                    f"Compositor rejected: {inference.app_id}/{inference.video_id} - "
                    f"{response_data.get('result', 'unknown')}"
                )

        except asyncio.TimeoutError:
            logger.warning(f"Timeout: {inference.app_id}/{inference.video_id}")
        except Exception as e:
            logger.warning(f"Failed: {inference.app_id}/{inference.video_id}: {e}")


@asynccontextmanager
async def nats_wakeup_lifespan() -> AsyncGenerator[NatsWakeupService, None]:
    """Lifespan context manager for NatsWakeupService.

    Usage in FastAPI lifespan:
        async with nats_wakeup_lifespan() as wakeup_service:
            yield
    """
    service = NatsWakeupService()
    await service.start()
    try:
        yield service
    finally:
        await service.stop()
