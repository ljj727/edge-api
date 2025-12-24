"""User management API endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUserRequired, DBSession
from app.schemas.auth import ChangePassword
from app.services.user_service import UserService

router = APIRouter()


@router.put("/{user_id}/password")
async def change_password(
    user_id: str,
    data: ChangePassword,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> dict:
    """
    Change user password.

    - **user_id**: User ID to change password for
    - **password**: New password
    """
    # Users can only change their own password
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change other user's password",
        )

    user_service = UserService(db)
    success = await user_service.change_password(user_id, data.password)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {"status": "success"}
