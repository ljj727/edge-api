"""Inference API endpoints."""

from fastapi import APIRouter, HTTPException, Query, Response, status
from loguru import logger
from sqlalchemy import select

from app.core.deps import CurrentUserRequired, DBSession
from app.grpc import get_grpc_client
from app.models.inference import Inference
from app.schemas.inference import (
    InferenceCreate,
    InferenceDTO,
    InferenceEventSettingUpdate,
    InferenceSettings,
    InferenceStreamStart,
    InferenceSyncResponse,
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

    - **videoId**: Filter by video ID (optional, returns all if not provided)
    """
    inference_service = _get_inference_service(db)
    return await inference_service.get_statuses(video_id)


@router.post("/sync", response_model=InferenceSyncResponse)
async def sync_inferences(
    db: DBSession,
    current_user: CurrentUserRequired,
) -> InferenceSyncResponse:
    """
    Sync inferences between Core and database.

    Bidirectional sync:
    - Core에만 있는 것 → DB에 추가
    - DB에만 있는 것 → Core에 추가 시도
    - Core에 없고 DB에만 있는 것 → DB에서 삭제 (Core가 source of truth)
    """
    grpc_client = get_grpc_client()
    if not grpc_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Core service not available",
        )

    # Get inferences from Core
    core_inferences = await grpc_client.get_inference_list()
    core_keys = {(inf["app_id"], inf["stream_id"]) for inf in core_inferences if inf.get("app_id") and inf.get("stream_id")}

    # Get inferences from DB
    result = await db.execute(select(Inference))
    db_inferences = {(inf.app_id, inf.video_id): inf for inf in result.scalars().all()}
    db_keys = set(db_inferences.keys())

    added_to_db = 0
    added_to_core = 0
    deleted_from_db = 0
    failed = 0

    # Core에만 있는 것 → DB에 추가
    only_in_core = core_keys - db_keys
    for app_id, video_id in only_in_core:
        # Find the core inference data
        core_inf = next(
            (inf for inf in core_inferences if inf.get("app_id") == app_id and inf.get("stream_id") == video_id),
            None
        )
        if core_inf:
            inference = Inference(
                app_id=app_id,
                video_id=video_id,
                uri=core_inf.get("uri", ""),
                name=core_inf.get("name"),
                settings=core_inf.get("settings"),
            )
            db.add(inference)
            added_to_db += 1
            logger.info(f"Inference {app_id}/{video_id} added to DB from Core")

    # DB에만 있는 것 → Core에 추가 시도 또는 DB에서 삭제
    only_in_db = db_keys - core_keys
    for app_id, video_id in only_in_db:
        db_inf = db_inferences[(app_id, video_id)]

        # Core에 추가 시도
        try:
            await grpc_client.add_inference(
                app_id=app_id,
                video_id=video_id,
                uri=db_inf.uri,
                name=db_inf.name,
            )
            added_to_core += 1
            logger.info(f"Inference {app_id}/{video_id} added to Core from DB")
        except Exception as e:
            # Core 추가 실패 시 DB에서도 삭제 (Core가 source of truth)
            logger.warning(f"Failed to add {app_id}/{video_id} to Core: {e}, deleting from DB")
            await db.delete(db_inf)
            deleted_from_db += 1

    await db.commit()

    total_changes = added_to_db + added_to_core + deleted_from_db
    message = f"Sync completed: {added_to_db} added to DB, {added_to_core} added to Core, {deleted_from_db} deleted from DB"
    logger.info(message)

    return InferenceSyncResponse(
        success=True,
        message=message,
        added_to_db=added_to_db,
        added_to_core=added_to_core,
        deleted_from_db=deleted_from_db,
        failed=failed,
    )
