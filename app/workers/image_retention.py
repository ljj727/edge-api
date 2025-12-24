"""Image retention worker for cleaning up old event images."""

from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import async_session_maker
from app.models.image import Image

settings = get_settings()


class ImageRetentionWorker:
    """Worker for cleaning up old event images based on retention policy."""

    def __init__(self, retention_days: int | None = None):
        self.retention_days = retention_days or settings.image_retention_days

    async def run(self) -> None:
        """Run the image retention cleanup."""
        logger.info(f"Running image retention cleanup (keeping {self.retention_days} days)")

        # Calculate cutoff timestamp
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        cutoff_ts = int(cutoff.timestamp() * 1000)  # Convert to milliseconds

        async with async_session_maker() as db:
            try:
                # Get images to delete
                result = await db.execute(
                    select(Image).where(Image.timestamp < cutoff_ts)
                )
                old_images = result.scalars().all()

                deleted_files = 0
                deleted_records = 0

                # Delete image files
                for image in old_images:
                    image_path = Path(settings.data_save_folder) / image.path
                    if image_path.exists():
                        try:
                            image_path.unlink()
                            deleted_files += 1
                        except OSError as e:
                            logger.warning(f"Failed to delete image file: {e}")

                # Delete database records
                result = await db.execute(
                    delete(Image).where(Image.timestamp < cutoff_ts)
                )
                await db.commit()
                deleted_records = result.rowcount

                logger.info(
                    f"Image retention: deleted {deleted_files} files, "
                    f"{deleted_records} records"
                )

            except Exception as e:
                logger.error(f"Image retention error: {e}")
                await db.rollback()
