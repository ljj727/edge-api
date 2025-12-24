"""Event retention worker for cleaning up old events."""

from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.session import async_session_maker
from app.models.event import Event

settings = get_settings()


class EventRetentionWorker:
    """Worker for cleaning up old events based on retention policy."""

    def __init__(self, retention_days: int | None = None):
        self.retention_days = retention_days or settings.event_retention_days

    async def run(self) -> None:
        """Run the retention cleanup."""
        logger.info(f"Running event retention cleanup (keeping {self.retention_days} days)")

        # Calculate cutoff timestamp
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        cutoff_ts = int(cutoff.timestamp() * 1000)  # Convert to milliseconds

        async with async_session_maker() as db:
            try:
                # Delete old events
                result = await db.execute(
                    delete(Event).where(Event.timestamp < cutoff_ts)
                )
                await db.commit()

                deleted_count = result.rowcount
                logger.info(f"Deleted {deleted_count} old events")

            except Exception as e:
                logger.error(f"Event retention error: {e}")
                await db.rollback()
