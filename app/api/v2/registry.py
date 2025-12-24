"""Registry API endpoints."""

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.deps import CurrentUserRequired, DBSession
from app.schemas.registry import RegistryAppDTO, RegistryCreate, RegistryDTO
from app.services.registry_service import RegistryService

router = APIRouter()


@router.get("", response_model=list[RegistryDTO])
async def get_registries(
    db: DBSession,
    current_user: CurrentUserRequired,
) -> list[RegistryDTO]:
    """Get all app registries."""
    registry_service = RegistryService(db)
    return await registry_service.get_all_dto()


@router.post("", response_model=RegistryDTO)
async def create_registry(
    data: RegistryCreate,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> RegistryDTO:
    """
    Create registry account.

    - **ip**: Registry server IP
    - **port**: Registry server port
    - **userId**: Registry username
    - **userPw**: Registry password
    """
    registry_service = RegistryService(db)
    return await registry_service.create_registry(data)


@router.delete("")
async def delete_registry(
    db: DBSession,
    current_user: CurrentUserRequired,
    registry_id: int = Query(..., alias="id"),
) -> dict:
    """
    Delete registry.

    - **id**: Registry ID to delete
    """
    registry_service = RegistryService(db)
    success = await registry_service.delete_by_id(registry_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registry not found",
        )

    return {"status": "success"}


@router.get("/{registry_id}/apps", response_model=list[RegistryAppDTO])
async def get_registry_apps(
    registry_id: int,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> list[RegistryAppDTO]:
    """
    Get apps from registry.

    - **registry_id**: Registry ID
    """
    registry_service = RegistryService(db)
    return await registry_service.get_apps(registry_id)


@router.post("/{registry_id}/app/{app_id}")
async def add_app_from_registry(
    registry_id: int,
    app_id: str,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> dict:
    """
    Add app from registry.

    - **registry_id**: Registry ID
    - **app_id**: App ID in registry
    """
    registry_service = RegistryService(db)
    app_data = await registry_service.download_app(registry_id, app_id)

    if not app_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="App not found in registry",
        )

    # TODO: Install app via gRPC

    return {"status": "success"}


@router.put("/{registry_id}/app/{app_id}")
async def update_app_from_registry(
    registry_id: int,
    app_id: str,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> dict:
    """
    Update app from registry.

    - **registry_id**: Registry ID
    - **app_id**: App ID in registry
    """
    registry_service = RegistryService(db)
    app_data = await registry_service.download_app(registry_id, app_id)

    if not app_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="App not found in registry",
        )

    # TODO: Update app via gRPC

    return {"status": "success"}


@router.get("/{registry_id}/app/{app_id}/cover")
async def get_registry_app_cover(
    registry_id: int,
    app_id: str,
    db: DBSession,
) -> Response:
    """
    Get app cover image from registry.

    - **registry_id**: Registry ID
    - **app_id**: App ID in registry
    """
    registry_service = RegistryService(db)
    image_data = await registry_service.get_app_cover_image(registry_id, app_id)

    if not image_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cover image not found",
        )

    return Response(
        content=image_data,
        media_type="image/png",
    )
