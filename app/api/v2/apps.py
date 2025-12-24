"""Apps API endpoints."""

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status

from app.core.deps import CurrentUserRequired, DBSession
from app.schemas.app import AppDTO

router = APIRouter()


@router.post("", response_model=AppDTO)
async def create_app(
    db: DBSession,
    current_user: CurrentUserRequired,
    file: UploadFile = File(...),
) -> AppDTO:
    """
    Register app from file.

    - **file**: App package file (unlimited size)
    """
    # Read file content
    content = await file.read()

    # TODO: Install app via gRPC
    # grpc_client.install_app(content)

    # Return placeholder
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="App installation not implemented - requires gRPC integration",
    )


@router.get("", response_model=list[AppDTO])
async def get_apps(
    db: DBSession,
    current_user: CurrentUserRequired,
) -> list[AppDTO]:
    """Get all registered apps."""
    # TODO: Get apps via gRPC
    # grpc_client.get_app_list()

    return []


@router.get("/{app_id}/cover")
async def get_app_cover(
    app_id: str,
    db: DBSession,
) -> Response:
    """
    Get app cover image.

    - **app_id**: App ID
    """
    # TODO: Get cover image from app storage

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Cover image not found",
    )


@router.put("/{app_id}", response_model=AppDTO)
async def update_app(
    app_id: str,
    db: DBSession,
    current_user: CurrentUserRequired,
    file: UploadFile = File(...),
) -> AppDTO:
    """
    Update app with file.

    - **app_id**: App ID to update
    - **file**: New app package file
    """
    content = await file.read()

    # TODO: Update app via gRPC

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="App update not implemented - requires gRPC integration",
    )


@router.delete("/{app_id}")
async def delete_app(
    app_id: str,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> dict:
    """
    Delete app.

    - **app_id**: App ID to delete
    """
    # TODO: Delete app via gRPC
    # grpc_client.uninstall_app(app_id)

    return {"status": "success"}
