"""NATS event subscriber for receiving detection events."""

import asyncio
import json
from typing import Any, Callable

import nats
from loguru import logger
from nats.aio.client import Client as NatsClient
from nats.aio.msg import Msg

from app.core.config import get_settings

settings = get_settings()


class NatsEventSubscriber:
    """NATS subscriber for detection events from Core."""

    def __init__(self):
        self._client: NatsClient | None = None
        self._subscriptions: list = []
        self._running = False
        self._event_handlers: list[Callable] = []

    async def connect(self) -> None:
        """Connect to NATS server."""
        try:
            self._client = await nats.connect(settings.nats_uri)
            logger.info(f"Connected to NATS at {settings.nats_uri}")
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        if self._client:
            for sub in self._subscriptions:
                await sub.unsubscribe()
            await self._client.close()
            self._client = None
            logger.info("Disconnected from NATS")

    def add_event_handler(self, handler: Callable) -> None:
        """Add event handler callback."""
        self._event_handlers.append(handler)

    async def subscribe_events(self, subject: str = "events.>") -> None:
        """Subscribe to event topics."""
        if not self._client:
            raise RuntimeError("Not connected to NATS")

        async def message_handler(msg: Msg) -> None:
            try:
                data = json.loads(msg.data.decode())
                await self._process_event(data, msg.subject)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode NATS message: {e}")
            except Exception as e:
                logger.error(f"Error processing NATS message: {e}")

        sub = await self._client.subscribe(subject, cb=message_handler)
        self._subscriptions.append(sub)
        logger.info(f"Subscribed to NATS subject: {subject}")

    async def subscribe_wakeup(self, subject: str = "wakeup.>") -> None:
        """Subscribe to wakeup signals."""
        if not self._client:
            raise RuntimeError("Not connected to NATS")

        async def wakeup_handler(msg: Msg) -> None:
            try:
                data = json.loads(msg.data.decode())
                logger.debug(f"Received wakeup signal: {data}")
            except Exception as e:
                logger.error(f"Error processing wakeup message: {e}")

        sub = await self._client.subscribe(subject, cb=wakeup_handler)
        self._subscriptions.append(sub)
        logger.info(f"Subscribed to NATS subject: {subject}")

    async def _process_event(self, data: dict[str, Any], subject: str) -> None:
        """Process received event."""
        logger.debug(f"Received event on {subject}: {data}")

        # Call all registered handlers
        for handler in self._event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    async def run(self) -> None:
        """Run the subscriber (blocking)."""
        await self.connect()
        await self.subscribe_events()
        await self.subscribe_wakeup()

        self._running = True
        logger.info("NATS subscriber running")

        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.disconnect()

    def stop(self) -> None:
        """Stop the subscriber."""
        self._running = False
