"""Media proxy API endpoints."""

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.core.deps import DBSession
from app.schemas.protocol import ProtocolDTO
from app.services.event_service import EventService

settings = get_settings()

router = APIRouter()


@router.get("/{media_tail:path}")
async def proxy_media(
    request: Request,
    media_tail: str,
    pos: int | None = Query(None),
    end_pos: int | None = Query(None, alias="endPos"),
    download: bool = Query(False),
) -> StreamingResponse:
    """
    Proxy media from ViveEX with Range support.

    - **media_tail**: Media path
    - **pos**: Start position (bytes)
    - **endPos**: End position (bytes)
    - **download**: Force download
    """
    # Build target URL
    base_url = settings.backend_base
    target_url = f"{base_url}/media/{media_tail}"

    # Build headers
    headers = {}

    # Auth priority: Bearer token > Basic auth > Client auth
    if settings.bearer_token:
        headers["Authorization"] = f"Bearer {settings.bearer_token}"
    elif settings.basic_user and settings.basic_pass:
        import base64
        credentials = f"{settings.basic_user}:{settings.basic_pass}"
        auth_header = base64.b64encode(credentials.encode()).decode()
        headers["Authorization"] = f"Basic {auth_header}"
    else:
        # Forward client auth
        auth = request.headers.get("Authorization")
        if auth:
            headers["Authorization"] = auth

    # Handle Range request
    range_header = request.headers.get("Range")
    if range_header:
        headers["Range"] = range_header
    elif pos is not None:
        if end_pos is not None:
            headers["Range"] = f"bytes={pos}-{end_pos}"
        else:
            headers["Range"] = f"bytes={pos}-"

    async def stream_media():
        async with httpx.AsyncClient(
            verify=False,
            timeout=httpx.Timeout(30.0, read=1800.0),
        ) as client:
            async with client.stream("GET", target_url, headers=headers) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk

    try:
        # Get response headers first
        async with httpx.AsyncClient(
            verify=False,
            timeout=httpx.Timeout(30.0),
        ) as client:
            head_response = await client.head(target_url, headers=headers)

        response_headers = {}
        if "Content-Type" in head_response.headers:
            response_headers["Content-Type"] = head_response.headers["Content-Type"]
        if "Content-Length" in head_response.headers:
            response_headers["Content-Length"] = head_response.headers["Content-Length"]
        if "Content-Range" in head_response.headers:
            response_headers["Content-Range"] = head_response.headers["Content-Range"]
        if "Accept-Ranges" in head_response.headers:
            response_headers["Accept-Ranges"] = head_response.headers["Accept-Ranges"]

        if download:
            response_headers["Content-Disposition"] = f"attachment; filename={media_tail.split('/')[-1]}"

        return StreamingResponse(
            stream_media(),
            status_code=head_response.status_code,
            headers=response_headers,
        )

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to proxy media: {str(e)}",
        )


@router.head("/{media_tail:path}")
async def head_media(
    request: Request,
    media_tail: str,
) -> Response:
    """
    HEAD request proxy for media.

    - **media_tail**: Media path
    """
    base_url = settings.backend_base
    target_url = f"{base_url}/media/{media_tail}"

    headers = {}
    if settings.bearer_token:
        headers["Authorization"] = f"Bearer {settings.bearer_token}"
    elif settings.basic_user and settings.basic_pass:
        import base64
        credentials = f"{settings.basic_user}:{settings.basic_pass}"
        auth_header = base64.b64encode(credentials.encode()).decode()
        headers["Authorization"] = f"Basic {auth_header}"

    try:
        async with httpx.AsyncClient(
            verify=False,
            timeout=httpx.Timeout(30.0),
        ) as client:
            response = await client.head(target_url, headers=headers)

        response_headers = dict(response.headers)
        return Response(
            status_code=response.status_code,
            headers=response_headers,
        )

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to proxy media: {str(e)}",
        )


# Statistics endpoints (reusing event service)
@router.get("")
async def get_media_statistics(
    db: DBSession,
    video_id: str | None = Query(None, alias="videoId"),
    start_time: int = Query(0, alias="startTime"),
    end_time: int = Query(0, alias="endTime"),
) -> list:
    """Get event statistics for media."""
    from app.schemas.event import EventQueryParams

    params = EventQueryParams(
        video_id=video_id,
        start_time=start_time,
        end_time=end_time,
    )

    event_service = EventService(db)
    summary = await event_service.get_event_summary(params)
    return [item.model_dump(by_alias=True) for item in summary.items]


@router.get("/protocol", response_model=ProtocolDTO | None)
async def get_media_protocol(
    db: DBSession,
) -> ProtocolDTO | None:
    """Get statistics protocol."""
    event_service = EventService(db)
    return await event_service.get_protocol("eventstatistics")


@router.post("/protocol", response_model=ProtocolDTO)
async def create_media_protocol(
    format_str: str,
    db: DBSession,
) -> ProtocolDTO:
    """Create or update statistics protocol."""
    event_service = EventService(db)
    return await event_service.create_or_update_protocol("eventstatistics", format_str)
