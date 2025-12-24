"""Video management API endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUserRequired, DBSession
from app.schemas.video import VideoCreate, VideoDTO, VideoSettings, VideoSettingUpdate
from app.services.video_service import VideoService

router = APIRouter()


@router.get("", response_model=list[VideoDTO])
async def get_videos(
    db: DBSession,
    current_user: CurrentUserRequired,
) -> list[VideoDTO]:
    """Get all videos/streams."""
    video_service = VideoService(db)
    return await video_service.get_all_dto()


@router.post("", response_model=VideoDTO)
async def create_video(
    data: VideoCreate,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> VideoDTO:
    """
    Create new video/stream.

    - **uri**: Stream URL (required)
    - **name**: Display name
    - **deviceId**: Device ID reference
    - **serverId**: Server ID reference
    - **settings**: Video settings (masking, detection point, etc.)
    """
    video_service = VideoService(db)
    return await video_service.create_video(data)


@router.patch("/{video_id}", response_model=VideoDTO)
async def update_video(
    video_id: str,
    name: str | None = None,
    db: DBSession = None,
    current_user: CurrentUserRequired = None,
) -> VideoDTO:
    """
    Update video name.

    - **video_id**: Video ID
    - **name**: New display name
    """
    video_service = VideoService(db)
    result = await video_service.update_video_name(video_id, name)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    return result


@router.put("/{video_id}/video-setting", response_model=VideoDTO)
async def update_video_settings(
    video_id: str,
    data: VideoSettingUpdate,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> VideoDTO:
    """
    Update video settings.

    - **video_id**: Video ID
    - **settings**: Video settings (masking region, detection point, etc.)
    """
    video_service = VideoService(db)
    result = await video_service.update_video_settings(video_id, data.settings)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    return result


@router.delete("/{video_id}")
async def delete_video(
    video_id: str,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> dict:
    """
    Delete video.

    - **video_id**: Video ID to delete
    """
    video_service = VideoService(db)
    success = await video_service.delete_video(video_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    return {"status": "success"}
