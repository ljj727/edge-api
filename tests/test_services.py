"""Tests for service layer."""

import json
import time

import pytest

from app.models.event import Event
from app.models.user import User
from app.models.video import Video
from app.schemas.event import EventQueryParams
from app.schemas.video import VideoCreate, VideoSettings
from app.services.auth_service import AuthService
from app.services.event_service import EventService
from app.services.user_service import UserService
from app.services.video_service import VideoService


@pytest.mark.asyncio
async def test_user_service_create(db_session):
    """Test user creation."""
    user_service = UserService(db_session)

    user = await user_service.create_user(
        user_id="new-user",
        username="newuser",
        password="password123",
        is_superuser=False,
    )

    assert user.id == "new-user"
    assert user.username == "newuser"
    assert user.is_superuser is False


@pytest.mark.asyncio
async def test_user_service_authenticate(db_session, admin_user: User):
    """Test user authentication."""
    user_service = UserService(db_session)

    # Valid credentials
    user = await user_service.authenticate("admin", "admin")
    assert user is not None
    assert user.id == "admin"

    # Invalid credentials
    user = await user_service.authenticate("admin", "wrong")
    assert user is None


@pytest.mark.asyncio
async def test_user_service_change_password(db_session, test_user: User):
    """Test password change."""
    user_service = UserService(db_session)

    result = await user_service.change_password(test_user.id, "newpassword")
    assert result is True

    # Verify new password works
    user = await user_service.authenticate("testuser", "newpassword")
    assert user is not None


@pytest.mark.asyncio
async def test_auth_service_login(db_session, admin_user: User):
    """Test auth service login."""
    auth_service = AuthService(db_session)

    token = await auth_service.login("admin", "admin")
    assert token is not None
    assert len(token.token) > 0


@pytest.mark.asyncio
async def test_video_service_crud(db_session):
    """Test video service CRUD operations."""
    video_service = VideoService(db_session)

    # Create
    video_data = VideoCreate(
        uri="rtsp://test:554/stream",
        name="Test Camera",
        device_id="cam-test",
        settings=VideoSettings(
            masking_region=[],
            detection_point="c:b",
            line_cross_point="c:c",
        ),
    )
    video = await video_service.create_video(video_data)
    assert video.uri == video_data.uri
    assert video.name == video_data.name

    # Read
    videos = await video_service.get_all_dto()
    assert len(videos) == 1

    # Update name
    updated = await video_service.update_video_name(video.id, "Updated Name")
    assert updated.name == "Updated Name"

    # Update settings
    new_settings = VideoSettings(
        masking_region=[[[0.1, 0.1], [0.9, 0.9]]],
        detection_point="c:c",
        line_cross_point="c:b",
    )
    updated = await video_service.update_video_settings(video.id, new_settings)
    assert updated.settings.detection_point == "c:c"

    # Delete
    result = await video_service.delete_video(video.id)
    assert result is True

    videos = await video_service.get_all_dto()
    assert len(videos) == 0


@pytest.mark.asyncio
async def test_event_service_get_events(db_session, sample_events: list[Event]):
    """Test event service get events."""
    event_service = EventService(db_session)

    params = EventQueryParams(
        paging_size=5,
        paging_index=1,
        order="desc",
    )

    result = await event_service.get_events(params)
    assert len(result.events) == 5
    assert result.total == len(sample_events)


@pytest.mark.asyncio
async def test_event_service_filter_by_object_type(
    db_session, sample_events: list[Event]
):
    """Test event filtering by object type."""
    event_service = EventService(db_session)

    params = EventQueryParams(object_type="person", paging_size=0)

    result = await event_service.get_events(params)

    for event in result.events:
        assert event.object_type == "person"


@pytest.mark.asyncio
async def test_event_service_get_summary(db_session, sample_events: list[Event]):
    """Test event summary."""
    event_service = EventService(db_session)

    params = EventQueryParams()
    result = await event_service.get_event_summary(params)

    assert len(result.items) > 0
    for item in result.items:
        assert item.count > 0


@pytest.mark.asyncio
async def test_event_service_get_trend(db_session, sample_events: list[Event]):
    """Test event trend."""
    event_service = EventService(db_session)

    params = EventQueryParams()
    result = await event_service.get_event_trend(params, unit="hour")

    assert isinstance(result.categories, list)
    assert isinstance(result.series, dict)
    assert isinstance(result.total, list)


@pytest.mark.asyncio
async def test_event_model_timestamp_normalization():
    """Test event timestamp normalization."""
    # 10 digit (seconds)
    event = Event(timestamp=1609459200)
    assert event.normalized_timestamp == 1609459200000

    # 13 digit (milliseconds)
    event = Event(timestamp=1609459200000)
    assert event.normalized_timestamp == 1609459200000

    # 16 digit (microseconds)
    event = Event(timestamp=1609459200000000)
    assert event.normalized_timestamp == 1609459200000


@pytest.mark.asyncio
async def test_event_model_objects_serialization():
    """Test event objects serialization."""
    event = Event()

    objects = [
        {"trackId": "1", "label": "person", "bbox": [0.1, 0.2, 0.3, 0.4]},
        {"trackId": "2", "label": "car", "bbox": [0.5, 0.6, 0.2, 0.2]},
    ]

    event.set_objects(objects)

    assert event.object_type == "person"  # First object's label
    assert event.objects is not None

    loaded = event.get_objects()
    assert len(loaded) == 2
    assert loaded[0]["label"] == "person"
