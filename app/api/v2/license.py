"""License API endpoints."""

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status

from app.core.deps import CurrentUserRequired, DBSession
from app.schemas.system import LicenseDownload

router = APIRouter()


@router.post("")
async def download_license_req(
    data: LicenseDownload,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> Response:
    """
    Download license request file (.req).

    - **licenseKey**: License key
    - **state**: License state
    """
    # TODO: Generate .req file via gRPC
    # grpc_client.license_activation(license_key, state)

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="License request not implemented - requires gRPC integration",
    )


@router.put("")
async def upload_license(
    db: DBSession,
    current_user: CurrentUserRequired,
    file: UploadFile = File(...),
) -> dict:
    """
    Upload license file (.lic).

    - **file**: License file
    """
    content = await file.read()

    # TODO: Activate license via gRPC
    # grpc_client.license_activate(content)

    return {"status": "success"}
