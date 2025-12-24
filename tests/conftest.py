"""Pytest configuration and fixtures."""

import asyncio
import json
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.deps import get_db
from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.db import models_registry  # noqa: F401 - Import to register models
from app.main import app
from app.models.event import Event
from app.models.eventpush import Eventpush
from app.models.inference import Inference
from app.models.user import User
from app.models.video import Video

# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with overridden dependencies."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """Create test user."""
    # Use a simple hash for testing to avoid bcrypt issues
    import hashlib
    simple_hash = hashlib.sha256(b"testpassword").hexdigest()
    user = User(
        id="test-user",
        username="testuser",
        hashed_password=f"$plain${simple_hash}",  # Mark as plain for testing
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def admin_user(db_session: AsyncSession) -> User:
    """Create admin user."""
    # Use a simple hash for testing to avoid bcrypt issues
    import hashlib
    simple_hash = hashlib.sha256(b"admin").hexdigest()
    user = User(
        id="admin",
        username="admin",
        hashed_password=f"$plain${simple_hash}",  # Mark as plain for testing
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Create authorization headers."""
    token = create_access_token(
        data={"sub": test_user.id, "username": test_user.username}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(admin_user: User) -> dict:
    """Create admin authorization headers."""
    token = create_access_token(
        data={"sub": admin_user.id, "username": admin_user.username}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def sample_videos(db_session: AsyncSession) -> list[Video]:
    """Create sample videos."""
    videos = [
        Video(
            id="video-001",
            uri="rtsp://192.168.1.100:554/stream1",
            name="Main Entrance",
            device_id="cam-001",
            server_id="server-001",
            settings=json.dumps({
                "maskingRegion": [],
                "detectionPoint": "c:b",
                "lineCrossPoint": "c:c",
            }),
        ),
        Video(
            id="video-002",
            uri="rtsp://192.168.1.101:554/stream1",
            name="Parking Lot",
            device_id="cam-002",
            server_id="server-001",
            settings=json.dumps({
                "maskingRegion": [],
                "detectionPoint": "c:b",
                "lineCrossPoint": "c:c",
            }),
        ),
    ]

    for video in videos:
        db_session.add(video)
    await db_session.commit()

    return videos


@pytest_asyncio.fixture(scope="function")
async def sample_events(db_session: AsyncSession, sample_videos: list[Video]) -> list[Event]:
    """Create sample events."""
    import time

    now = int(time.time() * 1000)
    events = []

    for i in range(10):
        video = sample_videos[i % len(sample_videos)]
        objects = [
            {
                "trackId": f"track-{i}",
                "label": "person" if i % 2 == 0 else "car",
                "bbox": [0.1, 0.1, 0.2, 0.3],
                "score": 0.95,
                "classifiers": [],
            }
        ]

        event = Event(
            id=i + 1,  # Explicit ID for SQLite compatibility
            event_setting_id=f"event-{i:03d}",
            event_setting_name=f"Event Setting {i}",
            video_id=video.id,
            video_name=video.name,
            app_id="app-detection",
            timestamp=now - (i * 3600000),  # 1 hour apart
            caption=f"Detection {i}",
            desc=f"Event description {i}",
            device_id=video.device_id,
            vms_id="vms-001",
            objects=json.dumps(objects),
            object_type="person" if i % 2 == 0 else "car",
        )
        events.append(event)
        db_session.add(event)

    await db_session.commit()
    return events


@pytest_asyncio.fixture(scope="function")
async def sample_inferences(
    db_session: AsyncSession, sample_videos: list[Video]
) -> list[Inference]:
    """Create sample inferences."""
    inferences = [
        Inference(
            app_id="app-person-detection",
            video_id=sample_videos[0].id,
            uri="http://localhost:8080/v1/inference",
            name="Person Detection",
            type="detection",
            settings=json.dumps({
                "version": "1.6.1",
                "configs": [
                    {
                        "eventType": "intrusion",
                        "eventSettingId": "event-001",
                        "eventSettingName": "Intrusion Zone",
                        "points": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
                    }
                ],
            }),
        ),
    ]

    for inf in inferences:
        db_session.add(inf)
    await db_session.commit()

    return inferences


@pytest_asyncio.fixture(scope="function")
async def sample_eventpushes(db_session: AsyncSession) -> list[Eventpush]:
    """Create sample eventpushes."""
    eventpushes = [
        Eventpush(
            id="ep-001",
            name="Alert Webhook",
            url="http://localhost:9000/webhook/alerts",
            events=json.dumps(["person", "intrusion"]),
            enabled=True,
        ),
        Eventpush(
            id="ep-002",
            name="Vehicle Webhook",
            url="http://localhost:9000/webhook/vehicles",
            events=json.dumps(["car", "truck"]),
            enabled=False,
        ),
    ]

    for ep in eventpushes:
        db_session.add(ep)
    await db_session.commit()

    return eventpushes
