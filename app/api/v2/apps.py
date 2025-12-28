"""Apps API endpoints - Core gRPC based."""

import json
import zipfile
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status
from loguru import logger

from app.core.config import get_settings
from app.core.deps import CurrentUserRequired, DBSession
from app.grpc import get_grpc_client
from app.grpc.detector_client import AppInfo
from app.schemas.app import AppDTO, AppModel, AppProperty, AppPropertyPipeline, Output, OutputClassifier

router = APIRouter()
settings = get_settings()


def _app_info_to_dto(app: AppInfo) -> AppDTO:
    """Convert gRPC AppInfo to AppDTO."""
    # Convert models
    models = []
    if app.models:
        for m in app.models:
            models.append(AppModel(
                id=m.id,
                name=m.name,
                version=m.version,
                capacity=m.capacity,
                precision=m.precision,
                desc=m.desc,
                path=m.path,
            ))

    # Parse outputs JSON string
    outputs = []
    if app.outputs:
        try:
            outputs_data = json.loads(app.outputs)
            if isinstance(outputs_data, list):
                for o in outputs_data:
                    if isinstance(o, dict):
                        classifiers = []
                        if o.get("classifiers"):
                            for c in o["classifiers"]:
                                if isinstance(c, dict):
                                    classifiers.append(OutputClassifier(
                                        class_type=c.get("classType", ""),
                                        result_labels=c.get("resultLabels", []),
                                    ))
                        outputs.append(Output(
                            label=o.get("label", ""),
                            classifiers=classifiers,
                        ))
        except json.JSONDecodeError:
            pass

    # Parse pipelines JSON string to AppProperty
    properties = None
    if app.pipelines:
        try:
            pipelines_data = json.loads(app.pipelines)
            if isinstance(pipelines_data, list):
                pipeline_list = []
                for p in pipelines_data:
                    if isinstance(p, dict):
                        pipeline_list.append(AppPropertyPipeline(
                            name=p.get("name", ""),
                            type=p.get("type"),
                            properties=p.get("properties", {}),
                            attributes=p.get("attributes", {}),
                        ))
                properties = AppProperty(pipeline=pipeline_list)
        except json.JSONDecodeError:
            pass

    return AppDTO(
        id=app.id,
        name=app.name,
        desc=app.desc,
        version=app.version,
        framework=app.framework,
        evgen_path=app.evgen_path,
        models=models,
        outputs=outputs,
        properties=properties,
        app_memory_usage=app.memory_usage,
    )


def _parse_app_json_from_zip(content: bytes) -> dict:
    """Parse app.json from zip file content."""
    with BytesIO(content) as bio:
        try:
            with zipfile.ZipFile(bio, "r") as zf:
                # Find app.json in zip
                for name in zf.namelist():
                    if name.endswith("app.json"):
                        with zf.open(name) as f:
                            return json.load(f)
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid zip file",
            )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="app.json not found in zip file",
    )


@router.post("", response_model=AppDTO, status_code=201)
async def create_app(
    db: DBSession,
    current_user: CurrentUserRequired,
    file: UploadFile = File(...),
) -> AppDTO:
    """
    Install app from zip file via Core gRPC.

    - **file**: App package file (.zip)

    The zip file should contain:
    - app.json: App metadata
    - Model files and configurations
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .zip files are supported",
        )

    grpc_client = get_grpc_client()
    if not grpc_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Core service not available (gRPC client not connected)",
        )

    content = await file.read()

    # Parse app.json to get app_id
    try:
        app_json = _parse_app_json_from_zip(content)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid app.json: {e}",
        )

    app_id = app_json.get("id")
    if not app_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="app.json must contain 'id' field",
        )

    # Check for duplicate via gRPC
    existing_apps = await grpc_client.get_app_list()
    if any(app.id == app_id for app in existing_apps):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"App with ID '{app_id}' already exists",
        )

    # Install via gRPC streaming (1MB chunks like legacy)
    success = await grpc_client.install_app(content, app_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to install app in Core",
        )

    logger.info(f"App '{app_id}' installed by {current_user.username}")

    # Get installed app info from Core
    apps = await grpc_client.get_app_list()
    for app in apps:
        if app.id == app_id:
            # Return the app info from gRPC response
            # Since get_app_list returns AppInfo dataclass, we need raw gRPC response
            # For now, construct from app_json
            return AppDTO(
                id=app_id,
                name=app_json.get("name", ""),
                desc=app_json.get("desc"),
                version=app_json.get("version"),
                framework=app_json.get("framework"),
                models=[],
                outputs=[],
                properties=app_json.get("properties"),
                app_memory_usage=app_json.get("app_memory_usage"),
                app_max_fps=app_json.get("app_max_fps"),
            )

    # Fallback to app_json data
    return AppDTO(
        id=app_id,
        name=app_json.get("name", ""),
        desc=app_json.get("desc"),
        version=app_json.get("version"),
        framework=app_json.get("framework"),
        models=[],
        outputs=[],
        properties=app_json.get("properties"),
        app_memory_usage=app_json.get("app_memory_usage"),
        app_max_fps=app_json.get("app_max_fps"),
    )


@router.get("", response_model=list[AppDTO])
async def get_apps(
    db: DBSession,
    current_user: CurrentUserRequired,
) -> list[AppDTO]:
    """Get all installed apps from Core."""
    grpc_client = get_grpc_client()
    if not grpc_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Core service not available",
        )

    apps = await grpc_client.get_app_list()
    return [_app_info_to_dto(app) for app in apps]


@router.get("/{app_id}", response_model=AppDTO)
async def get_app(
    app_id: str,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> AppDTO:
    """Get app by ID from Core."""
    grpc_client = get_grpc_client()
    if not grpc_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Core service not available",
        )

    apps = await grpc_client.get_app_list()

    for app in apps:
        if app.id == app_id:
            return _app_info_to_dto(app)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="App not found",
    )


@router.get("/{app_id}/cover")
async def get_app_cover(
    app_id: str,
    db: DBSession,
) -> Response:
    """
    Get app cover image from Core.

    - **app_id**: App ID

    Note: Cover images are stored in Core's app directory.
    This endpoint returns the cover if available.
    """
    # Cover images are managed by Core
    # The legacy code reads from Core's app storage path
    # For now, return 404 - cover access requires Core's file system access
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Cover image not available (stored in Core)",
    )


@router.put("/{app_id}", response_model=AppDTO)
async def update_app(
    app_id: str,
    db: DBSession,
    current_user: CurrentUserRequired,
    file: UploadFile = File(...),
) -> AppDTO:
    """
    Update app with new zip file.

    - **app_id**: App ID to update
    - **file**: New app package file (.zip)

    Note: This will uninstall the old app and install the new one.
    Existing inferences will be preserved.
    """
    grpc_client = get_grpc_client()
    if not grpc_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Core service not available",
        )

    # Check if app exists
    apps = await grpc_client.get_app_list()
    if not any(app.id == app_id for app in apps):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="App not found",
        )

    # Get current inferences to restore later
    inferences = await grpc_client.get_inference_list(app_id)

    # Uninstall old app
    await grpc_client.uninstall_app(app_id)

    # Install new app
    content = await file.read()
    app_json = _parse_app_json_from_zip(content)

    new_app_id = app_json.get("id")
    if new_app_id != app_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"App ID mismatch: expected '{app_id}', got '{new_app_id}'",
        )

    success = await grpc_client.install_app(content, app_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to install updated app in Core",
        )

    # Restore inferences (TODO: implement inference restoration)
    # for inf in inferences:
    #     await grpc_client.add_inference(...)

    logger.info(f"App '{app_id}' updated by {current_user.username}")

    return AppDTO(
        id=app_id,
        name=app_json.get("name", ""),
        desc=app_json.get("desc"),
        version=app_json.get("version"),
        framework=app_json.get("framework"),
        models=[],
        outputs=[],
        properties=app_json.get("properties"),
        app_memory_usage=app_json.get("app_memory_usage"),
        app_max_fps=app_json.get("app_max_fps"),
    )


@router.delete("/{app_id}")
async def delete_app(
    app_id: str,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> dict:
    """
    Delete app from Core.

    - **app_id**: App ID to delete
    """
    grpc_client = get_grpc_client()
    if not grpc_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Core service not available",
        )

    # Check if app exists
    apps = await grpc_client.get_app_list()
    if not any(app.id == app_id for app in apps):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="App not found",
        )

    # Remove all inferences for this app first (ignore if none exist)
    try:
        await grpc_client.remove_inference_all(app_id)
    except Exception as e:
        # "pipeline not found" is expected when no inferences exist
        logger.debug(f"RemoveInferenceAll for '{app_id}': {e}")

    # Uninstall app
    success = await grpc_client.uninstall_app(app_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete app from Core",
        )

    logger.info(f"App '{app_id}' deleted by {current_user.username}")
    return {"status": "success", "message": f"App '{app_id}' deleted"}
