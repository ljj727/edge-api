"""Inference API endpoints."""

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.deps import CurrentUserRequired, DBSession
from app.grpc import get_grpc_client
from app.schemas.inference import (
    InferenceCreate,
    InferenceDTO,
    InferenceEventSettingUpdate,
    InferenceSettings,
    InferenceStreamStart,
    InferenceWithStatus,
)
from app.services.inference_service import InferenceService

router = APIRouter()


def _get_inference_service(db) -> InferenceService:
    """Get inference service with gRPC client."""
    return InferenceService(db, grpc_client=get_grpc_client())


@router.get("", response_model=list[InferenceDTO])
async def get_inferences(
    db: DBSession,
    current_user: CurrentUserRequired,
    video_id: str | None = Query(None, alias="videoId"),
) -> list[InferenceDTO]:
    """
    Get inferences for a video.

    - **videoId**: Filter by video ID
    """
    inference_service = _get_inference_service(db)

    if video_id:
        return await inference_service.get_by_video_id(video_id)

    # Get all inferences
    inferences = await inference_service.get_all()
    return [inference_service._to_dto(i) for i in inferences]


@router.post("", response_model=InferenceDTO)
async def create_inference(
    data: InferenceCreate,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> InferenceDTO:
    """
    Create new inference configuration.

    - **appId**: Application ID (required)
    - **videoId**: Video ID (required)
    - **uri**: Inference server URI (required)
    - **settings**: Inference settings (event configs, etc.)
    """
    inference_service = _get_inference_service(db)
    return await inference_service.create_inference(data)


@router.delete("")
async def delete_inference(
    db: DBSession,
    current_user: CurrentUserRequired,
    app_id: str = Query(..., alias="appId"),
    video_id: str = Query(..., alias="videoId"),
) -> dict:
    """
    Delete inference configuration.

    - **appId**: Application ID
    - **videoId**: Video ID
    """
    inference_service = _get_inference_service(db)
    success = await inference_service.remove_inference(app_id, video_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inference not found",
        )

    return {"status": "success"}


@router.put("/event-setting", response_model=InferenceDTO)
async def update_event_setting(
    data: InferenceEventSettingUpdate,
    db: DBSession,
    current_user: CurrentUserRequired,
    app_id: str = Query(..., alias="appId"),
    video_id: str = Query(..., alias="videoId"),
) -> InferenceDTO:
    """
    Update inference event settings.

    - **appId**: Application ID
    - **videoId**: Video ID
    - **settings**: New inference settings
    """
    inference_service = _get_inference_service(db)
    result = await inference_service.update_event_setting(
        app_id, video_id, data.settings
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inference not found",
        )

    return result


@router.get("/preview")
async def get_preview(
    db: DBSession,
    current_user: CurrentUserRequired,
    app_id: str = Query(..., alias="appId"),
    video_id: str = Query(..., alias="videoId"),
) -> Response:
    """
    Get preview image from inference.

    - **appId**: Application ID
    - **videoId**: Video ID
    """
    inference_service = _get_inference_service(db)
    image_data = await inference_service.get_preview_image(app_id, video_id)

    if not image_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preview not available",
        )

    return Response(
        content=image_data,
        media_type="image/jpeg",
    )


@router.post("/stream", response_model=InferenceStreamStart)
async def start_stream(
    db: DBSession,
    current_user: CurrentUserRequired,
    app_id: str = Query(..., alias="appId"),
    video_id: str = Query(..., alias="videoId"),
    uri: str = Query(...),
) -> InferenceStreamStart:
    """
    Start streaming from inference.

    - **appId**: Application ID
    - **videoId**: Video ID
    - **uri**: Stream URI
    """
    inference_service = _get_inference_service(db)
    result = await inference_service.start_stream(app_id, video_id, uri)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start stream",
        )

    return InferenceStreamStart(**result)


@router.delete("/stream")
async def stop_stream(
    db: DBSession,
    current_user: CurrentUserRequired,
    session_id: str = Query(..., alias="sessionId"),
) -> dict:
    """
    Stop streaming.

    - **sessionId**: Stream session ID
    """
    inference_service = _get_inference_service(db)
    success = await inference_service.stop_stream(session_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop stream",
        )

    return {"status": "success"}


@router.get("/status", response_model=list[InferenceWithStatus])
async def get_inference_status(
    db: DBSession,
    current_user: CurrentUserRequired,
    video_id: str | None = Query(None, alias="videoId"),
) -> list[InferenceWithStatus]:
    """
    Get inference status.

    - **videoId**: Filter by video ID
    """
    inference_service = _get_inference_service(db)

    if video_id:
        return await inference_service.get_statuses(video_id)

    return []
