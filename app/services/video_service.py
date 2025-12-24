"""Video service for stream management."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.video import Video
from app.schemas.video import VideoCreate, VideoDTO, VideoSettings
from app.services.base_service import BaseService


class VideoService(BaseService[Video]):
    """Video service for stream CRUD operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Video)

    async def get_all_dto(self) -> list[VideoDTO]:
        """Get all videos as DTOs."""
        videos = await self.get_all()
        return [self._to_dto(v) for v in videos]

    async def create_video(self, data: VideoCreate) -> VideoDTO:
        """Create new video."""
        video = Video(
            id=data.id or str(uuid.uuid4()),
            uri=data.uri,
            name=data.name,
            device_id=data.device_id,
            server_id=data.server_id,
        )
        if data.settings:
            video.set_settings(data.settings.model_dump(by_alias=True))
        video = await self.create(video)
        return self._to_dto(video)

    async def update_video_name(self, video_id: str, name: str | None) -> VideoDTO | None:
        """Update video name."""
        video = await self.get_by_id(video_id)
        if not video:
            return None
        video.name = name
        await self.update(video)
        return self._to_dto(video)

    async def update_video_settings(
        self, video_id: str, settings: VideoSettings
    ) -> VideoDTO | None:
        """Update video settings."""
        video = await self.get_by_id(video_id)
        if not video:
            return None
        video.set_settings(settings.model_dump(by_alias=True))
        await self.update(video)
        return self._to_dto(video)

    async def delete_video(self, video_id: str) -> bool:
        """Delete video by ID."""
        return await self.delete_by_id(video_id)

    def _to_dto(self, video: Video) -> VideoDTO:
        """Convert Video model to DTO."""
        settings_dict = video.get_settings()
        return VideoDTO(
            id=video.id,
            uri=video.uri,
            name=video.name,
            device_id=video.device_id,
            server_id=video.server_id,
            settings=VideoSettings(**settings_dict) if settings_dict else None,
        )
