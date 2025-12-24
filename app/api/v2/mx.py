"""Mx (ViveEX) API endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUserRequired, DBSession
from app.schemas.mx import MxCreate, MxDTO
from app.services.mx_service import MxService

router = APIRouter()


@router.post("", response_model=MxDTO)
async def create_mx(
    data: MxCreate,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> MxDTO:
    """
    Add Mx (ViveEX) account.

    - **ip**: ViveEX server IP
    - **port**: ViveEX server port
    - **username**: ViveEX username
    - **password**: ViveEX password
    """
    mx_service = MxService(db)
    return await mx_service.create_mx(data)


@router.get("", response_model=list[MxDTO])
async def get_mx_list(
    db: DBSession,
    current_user: CurrentUserRequired,
) -> list[MxDTO]:
    """Get all Mx (ViveEX) accounts."""
    mx_service = MxService(db)
    return await mx_service.get_all_dto()


@router.patch("/{mx_id}", response_model=MxDTO)
async def update_mx(
    mx_id: int,
    data: MxCreate,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> MxDTO:
    """
    Update Mx (ViveEX) account.

    - **mx_id**: Mx account ID
    """
    mx_service = MxService(db)
    result = await mx_service.update_mx(mx_id, data)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mx not found",
        )

    return result


@router.delete("/{mx_id}")
async def delete_mx(
    mx_id: int,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> dict:
    """
    Delete Mx (ViveEX) account.

    - **mx_id**: Mx account ID
    """
    mx_service = MxService(db)
    success = await mx_service.delete_mx(mx_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mx not found",
        )

    return {"success": True, "message": f"Mx '{mx_id}' deleted"}


@router.put("/{mx_id}/videos")
async def sync_mx_videos(
    mx_id: int,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> dict:
    """
    Sync videos from Mx (ViveEX).

    - **mx_id**: Mx account ID
    """
    mx_service = MxService(db)
    devices = await mx_service.get_devices(mx_id)

    # TODO: Sync devices to videos table

    return {"status": "success", "devices": len(devices)}
