"""Database seeder for mock data."""

import asyncio
import json
import random
import uuid
from datetime import datetime, timedelta

from loguru import logger

from app.core.security import get_password_hash
from app.db.base import Base
from app.db import models_registry  # noqa: F401 - Import to register models
from app.db.session import async_session_maker, engine
from app.models.event import Event
from app.models.eventpush import Eventpush
from app.models.inference import Inference
from app.models.mx import Mx
from app.models.protocol import Protocol
from app.models.registry import Registry
from app.models.user import User
from app.models.video import Video


async def create_tables():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables created")


async def seed_users():
    """Seed users."""
    users = [
        User(
            id="admin",
            username="admin",
            hashed_password=get_password_hash("admin"),
            is_active=True,
            is_superuser=True,
        ),
        User(
            id="user1",
            username="operator",
            hashed_password=get_password_hash("operator123"),
            is_active=True,
            is_superuser=False,
        ),
        User(
            id="user2",
            username="viewer",
            hashed_password=get_password_hash("viewer123"),
            is_active=True,
            is_superuser=False,
        ),
    ]

    async with async_session_maker() as db:
        for user in users:
            existing = await db.get(User, user.id)
            if not existing:
                db.add(user)
        await db.commit()
    logger.info(f"Seeded {len(users)} users")


async def seed_videos():
    """Seed videos/streams."""
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
            name="Parking Lot A",
            device_id="cam-002",
            server_id="server-001",
            settings=json.dumps({
                "maskingRegion": [[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]],
                "detectionPoint": "c:b",
                "lineCrossPoint": "c:c",
            }),
        ),
        Video(
            id="video-003",
            uri="rtsp://192.168.1.102:554/stream1",
            name="Loading Dock",
            device_id="cam-003",
            server_id="server-001",
            settings=json.dumps({
                "maskingRegion": [],
                "detectionPoint": "c:c",
                "lineCrossPoint": "c:c",
            }),
        ),
        Video(
            id="video-004",
            uri="rtsp://192.168.1.103:554/stream1",
            name="Warehouse Interior",
            device_id="cam-004",
            server_id="server-002",
            settings=json.dumps({
                "maskingRegion": [],
                "detectionPoint": "c:b",
                "lineCrossPoint": "c:b",
            }),
        ),
        Video(
            id="video-005",
            uri="rtsp://192.168.1.104:554/stream1",
            name="Back Gate",
            device_id="cam-005",
            server_id="server-002",
            settings=json.dumps({
                "maskingRegion": [],
                "detectionPoint": "c:b",
                "lineCrossPoint": "c:c",
            }),
        ),
    ]

    async with async_session_maker() as db:
        for video in videos:
            existing = await db.get(Video, video.id)
            if not existing:
                db.add(video)
        await db.commit()
    logger.info(f"Seeded {len(videos)} videos")


async def seed_inferences():
    """Seed inference configurations."""
    inferences = [
        Inference(
            app_id="app-person-detection",
            video_id="video-001",
            uri="http://localhost:8080/v1/inference",
            name="Person Detection - Main Entrance",
            type="detection",
            settings=json.dumps({
                "version": "1.6.1",
                "configs": [
                    {
                        "eventType": "intrusion",
                        "eventSettingId": "event-001",
                        "eventSettingName": "Intrusion Zone A",
                        "points": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
                        "target": {"labels": ["person"], "classifiers": {}},
                    }
                ],
            }),
        ),
        Inference(
            app_id="app-vehicle-detection",
            video_id="video-002",
            uri="http://localhost:8080/v1/inference",
            name="Vehicle Detection - Parking",
            type="detection",
            settings=json.dumps({
                "version": "1.6.1",
                "configs": [
                    {
                        "eventType": "counting",
                        "eventSettingId": "event-002",
                        "eventSettingName": "Vehicle Count",
                        "points": [[0.1, 0.5], [0.9, 0.5]],
                        "target": {"labels": ["car", "truck", "bus"], "classifiers": {}},
                    }
                ],
            }),
        ),
        Inference(
            app_id="app-person-detection",
            video_id="video-003",
            uri="http://localhost:8080/v1/inference",
            name="Person Detection - Loading Dock",
            type="detection",
            settings=json.dumps({
                "version": "1.6.1",
                "configs": [
                    {
                        "eventType": "loitering",
                        "eventSettingId": "event-003",
                        "eventSettingName": "Loitering Detection",
                        "points": [[0.3, 0.3], [0.7, 0.3], [0.7, 0.7], [0.3, 0.7]],
                        "target": {"labels": ["person"], "classifiers": {}},
                        "timeout": 30,
                    }
                ],
            }),
        ),
    ]

    async with async_session_maker() as db:
        for inf in inferences:
            existing = await db.get(Inference, (inf.app_id, inf.video_id))
            if not existing:
                db.add(inf)
        await db.commit()
    logger.info(f"Seeded {len(inferences)} inferences")


async def seed_events():
    """Seed detection events."""
    video_ids = ["video-001", "video-002", "video-003", "video-004", "video-005"]
    video_names = ["Main Entrance", "Parking Lot A", "Loading Dock", "Warehouse Interior", "Back Gate"]
    object_types = ["person", "car", "truck", "bicycle", "motorcycle"]
    event_types = ["intrusion", "counting", "loitering", "line_cross"]

    events = []
    now = datetime.now()

    # Generate 500 events over the last 7 days
    for i in range(500):
        video_idx = random.randint(0, len(video_ids) - 1)
        obj_type = random.choice(object_types)
        event_type = random.choice(event_types)

        # Random timestamp within last 7 days
        random_hours = random.randint(0, 7 * 24)
        timestamp = int((now - timedelta(hours=random_hours)).timestamp() * 1000)

        # Random bbox
        x = random.uniform(0.1, 0.7)
        y = random.uniform(0.1, 0.7)
        w = random.uniform(0.1, 0.3)
        h = random.uniform(0.1, 0.4)

        objects = [
            {
                "trackId": f"track-{random.randint(1000, 9999)}",
                "label": obj_type,
                "bbox": [x, y, w, h],
                "score": random.uniform(0.7, 0.99),
                "classifiers": [],
            }
        ]

        # Sometimes add multiple objects
        if random.random() > 0.7:
            obj_type2 = random.choice(object_types)
            objects.append({
                "trackId": f"track-{random.randint(1000, 9999)}",
                "label": obj_type2,
                "bbox": [x + 0.2, y, w, h],
                "score": random.uniform(0.7, 0.99),
                "classifiers": [],
            })

        event = Event(
            event_setting_id=f"event-{random.randint(1, 10):03d}",
            event_setting_name=f"{event_type.replace('_', ' ').title()} Zone",
            video_id=video_ids[video_idx],
            video_name=video_names[video_idx],
            app_id=f"app-{obj_type}-detection",
            timestamp=timestamp,
            caption=f"{obj_type.title()} detected",
            desc=f"{event_type.replace('_', ' ').title()} event detected at {video_names[video_idx]}",
            device_id=f"cam-{video_idx + 1:03d}",
            vms_id="vms-001",
            objects=json.dumps(objects),
            object_type=obj_type,
        )
        events.append(event)

    async with async_session_maker() as db:
        db.add_all(events)
        await db.commit()
    logger.info(f"Seeded {len(events)} events")


async def seed_eventpushes():
    """Seed webhook configurations."""
    eventpushes = [
        Eventpush(
            id=str(uuid.uuid4()),
            name="Alert Webhook",
            url="http://localhost:9000/webhook/alerts",
            events=json.dumps(["person", "intrusion"]),
            enabled=True,
        ),
        Eventpush(
            id=str(uuid.uuid4()),
            name="Vehicle Webhook",
            url="http://localhost:9000/webhook/vehicles",
            events=json.dumps(["car", "truck", "bus"]),
            enabled=True,
        ),
        Eventpush(
            id=str(uuid.uuid4()),
            name="All Events Webhook",
            url="http://localhost:9000/webhook/all",
            events=json.dumps([]),
            enabled=False,
        ),
    ]

    async with async_session_maker() as db:
        for ep in eventpushes:
            db.add(ep)
        await db.commit()
    logger.info(f"Seeded {len(eventpushes)} eventpushes")


async def seed_mx():
    """Seed ViveEX configurations."""
    mx_list = [
        Mx(
            name="ViveEX Primary",
            ip="192.168.1.200",
            port="7001",
            username="admin",
            password="admin123",
        ),
        Mx(
            name="ViveEX Secondary",
            ip="192.168.1.201",
            port="7001",
            username="admin",
            password="admin123",
        ),
    ]

    async with async_session_maker() as db:
        for mx in mx_list:
            db.add(mx)
        await db.commit()
    logger.info(f"Seeded {len(mx_list)} mx configurations")


async def seed_registries():
    """Seed registry configurations."""
    registries = [
        Registry(
            ip="registry.example.com",
            port="8080",
            user_id="admin",
            user_pw="admin123",
            token=None,
        ),
    ]

    async with async_session_maker() as db:
        for reg in registries:
            db.add(reg)
        await db.commit()
    logger.info(f"Seeded {len(registries)} registries")


async def seed_protocols():
    """Seed protocol configurations."""
    protocols = [
        Protocol(
            type="eventpolling",
            format=json.dumps({
                "id": "id",
                "timestamp": "timestamp",
                "camera": "videoName",
                "type": "objectType",
                "objects": "objects",
            }),
        ),
        Protocol(
            type="eventhook",
            format=json.dumps({
                "event_id": "id",
                "time": "timestamp",
                "stream": "videoId",
                "event_type": "objectType",
                "description": "desc",
            }),
        ),
        Protocol(
            type="eventstatistics",
            format=json.dumps({
                "camera": "camera",
                "videoId": "videoId",
                "type": "type",
                "count": "count",
            }),
        ),
    ]

    async with async_session_maker() as db:
        for protocol in protocols:
            db.add(protocol)
        await db.commit()
    logger.info(f"Seeded {len(protocols)} protocols")


async def seed_all():
    """Seed all mock data."""
    logger.info("Starting database seeding...")

    await create_tables()
    await seed_users()
    await seed_videos()
    await seed_inferences()
    await seed_events()
    await seed_eventpushes()
    await seed_mx()
    await seed_registries()
    await seed_protocols()

    logger.info("Database seeding completed!")


async def clear_all():
    """Clear all data from tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("All tables cleared and recreated")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--clear":
        asyncio.run(clear_all())
    else:
        asyncio.run(seed_all())
