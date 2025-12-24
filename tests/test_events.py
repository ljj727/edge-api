"""Tests for event endpoints."""

import pytest
from httpx import AsyncClient

from app.models.event import Event
from app.models.video import Video


@pytest.mark.asyncio
async def test_get_events(client: AsyncClient, sample_events: list[Event]):
    """Test getting paginated events."""
    response = await client.get("/api/v2/events")

    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert "total" in data
    assert "offset" in data
    assert "limit" in data
    assert len(data["events"]) <= 10  # Default page size


@pytest.mark.asyncio
async def test_get_events_with_pagination(client: AsyncClient, sample_events: list[Event]):
    """Test event pagination."""
    response = await client.get(
        "/api/v2/events",
        params={"pagingSize": 5, "pagingIndex": 1},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 5


@pytest.mark.asyncio
async def test_get_events_filter_by_video(
    client: AsyncClient, sample_events: list[Event], sample_videos: list[Video]
):
    """Test filtering events by video ID."""
    video_id = sample_videos[0].id

    response = await client.get(
        "/api/v2/events",
        params={"videoId": video_id},
    )

    assert response.status_code == 200
    data = response.json()

    # All returned events should have the specified video ID
    for event in data["events"]:
        assert event["videoId"] == video_id


@pytest.mark.asyncio
async def test_get_events_filter_by_object_type(
    client: AsyncClient, sample_events: list[Event]
):
    """Test filtering events by object type."""
    response = await client.get(
        "/api/v2/events",
        params={"objectType": "person"},
    )

    assert response.status_code == 200
    data = response.json()

    for event in data["events"]:
        assert event["objectType"] == "person"


@pytest.mark.asyncio
async def test_get_events_order_asc(client: AsyncClient, sample_events: list[Event]):
    """Test event ordering (ascending)."""
    response = await client.get(
        "/api/v2/events",
        params={"order": "asc"},
    )

    assert response.status_code == 200
    data = response.json()

    if len(data["events"]) > 1:
        timestamps = [e["timestamp"] for e in data["events"]]
        assert timestamps == sorted(timestamps)


@pytest.mark.asyncio
async def test_get_events_order_desc(client: AsyncClient, sample_events: list[Event]):
    """Test event ordering (descending)."""
    response = await client.get(
        "/api/v2/events",
        params={"order": "desc"},
    )

    assert response.status_code == 200
    data = response.json()

    if len(data["events"]) > 1:
        timestamps = [e["timestamp"] for e in data["events"]]
        assert timestamps == sorted(timestamps, reverse=True)


@pytest.mark.asyncio
async def test_get_event_summary(client: AsyncClient, sample_events: list[Event]):
    """Test event summary endpoint."""
    response = await client.get("/api/v2/events/summary")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_event_trend(client: AsyncClient, sample_events: list[Event]):
    """Test event trend endpoint."""
    response = await client.get(
        "/api/v2/events/trend",
        params={"unit": "hour"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert "series" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_event_trend_by_day(client: AsyncClient, sample_events: list[Event]):
    """Test event trend by day."""
    response = await client.get(
        "/api/v2/events/trend",
        params={"unit": "day"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "categories" in data


@pytest.mark.asyncio
async def test_get_events_with_time_range(
    client: AsyncClient, sample_events: list[Event]
):
    """Test filtering events by time range."""
    import time

    now = int(time.time() * 1000)
    start_time = now - (3 * 3600000)  # 3 hours ago

    response = await client.get(
        "/api/v2/events",
        params={"startTime": start_time, "endTime": now},
    )

    assert response.status_code == 200
    data = response.json()

    for event in data["events"]:
        assert event["timestamp"] >= start_time
        assert event["timestamp"] <= now


@pytest.mark.asyncio
async def test_get_event_image_not_found(client: AsyncClient):
    """Test getting non-existent event image."""
    response = await client.get("/api/v2/events/99999/image")

    assert response.status_code == 404
