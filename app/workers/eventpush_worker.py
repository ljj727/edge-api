"""Eventpush worker for sending webhook notifications."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.eventpush import Eventpush
from app.schemas.eventpush import EventpushEventMsg, EventpushEventMsgStream
from app.schemas.event import EventObject


class EventpushWorker:
    """Worker for pushing events to registered webhooks."""

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """Start the worker."""
        self._running = True
        self._client = httpx.AsyncClient(timeout=30.0)
        logger.info("Eventpush worker started")

    async def stop(self) -> None:
        """Stop the worker."""
        self._running = False
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("Eventpush worker stopped")

    async def enqueue(self, event: dict[str, Any]) -> None:
        """Add event to push queue."""
        await self._queue.put(event)

    async def run(self) -> None:
        """Run the worker (blocking)."""
        await self.start()

        try:
            while self._running:
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0,
                    )
                    await self._process_event(event)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error processing event: {e}")
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def _process_event(self, event: dict[str, Any]) -> None:
        """Process and push event to registered webhooks."""
        async with async_session_maker() as db:
            # Get all enabled eventpushes
            from sqlalchemy import select
            result = await db.execute(
                select(Eventpush).where(Eventpush.enabled == True)
            )
            eventpushes = result.scalars().all()

            for eventpush in eventpushes:
                # Check if event type matches
                event_types = eventpush.get_events()
                event_type = event.get("object_type") or event.get("objectType")

                if event_types and event_type not in event_types:
                    continue

                # Build webhook payload
                payload = self._build_payload(event)

                # Send webhook
                await self._send_webhook(eventpush.url, payload)

    def _build_payload(self, event: dict[str, Any]) -> dict[str, Any]:
        """Build webhook payload from event."""
        objects = event.get("objects", [])
        if isinstance(objects, str):
            import json
            try:
                objects = json.loads(objects)
            except json.JSONDecodeError:
                objects = []

        msg = EventpushEventMsg(
            id=event.get("id", 0),
            stream=EventpushEventMsgStream(
                app_id=event.get("app_id", event.get("appId", "")),
                stream_id=event.get("video_id", event.get("videoId", "")),
            ),
            timestamp=event.get("timestamp", 0),
            event_type=event.get("object_type", event.get("objectType", "")),
            desc=event.get("desc"),
            objects=[EventObject(**obj) for obj in objects],
        )

        return msg.model_dump(by_alias=True)

    async def _send_webhook(
        self,
        url: str,
        payload: dict[str, Any],
    ) -> bool:
        """Send webhook POST request."""
        if not self._client:
            return False

        try:
            response = await self._client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code >= 400:
                logger.warning(
                    f"Webhook failed: {url} - {response.status_code}"
                )
                return False

            logger.debug(f"Webhook sent: {url}")
            return True

        except httpx.RequestError as e:
            logger.error(f"Webhook error: {url} - {e}")
            return False
