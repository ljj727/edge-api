"""Tests for eventpush (webhook) endpoints."""

import pytest
from httpx import AsyncClient

from app.models.eventpush import Eventpush


@pytest.mark.asyncio
async def test_get_eventpushes(
    client: AsyncClient, sample_eventpushes: list[Eventpush]
):
    """Test getting all eventpushes."""
    response = await client.get("/api/v2/eventpushes")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(sample_eventpushes)


@pytest.mark.asyncio
async def test_create_eventpush(client: AsyncClient):
    """Test creating an eventpush."""
    eventpush_data = {
        "name": "Test Webhook",
        "url": "http://localhost:9000/webhook/test",
        "events": ["person", "car"],
        "enabled": True,
    }

    response = await client.post(
        "/api/v2/eventpushes",
        json=eventpush_data,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == eventpush_data["name"]
    assert data["url"] == eventpush_data["url"]
    assert data["events"] == eventpush_data["events"]
    assert data["enabled"] == eventpush_data["enabled"]
    assert "id" in data


@pytest.mark.asyncio
async def test_create_eventpush_minimal(client: AsyncClient):
    """Test creating an eventpush with minimal data."""
    eventpush_data = {
        "name": "Minimal Webhook",
        "url": "http://localhost:9000/webhook/minimal",
    }

    response = await client.post(
        "/api/v2/eventpushes",
        json=eventpush_data,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == eventpush_data["name"]
    assert data["events"] == []
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_update_eventpush_events(
    client: AsyncClient, sample_eventpushes: list[Eventpush]
):
    """Test updating eventpush events."""
    ep = sample_eventpushes[0]
    new_events = {"events": ["truck", "bicycle", "motorcycle"]}

    response = await client.put(
        f"/api/v2/eventpushes/{ep.id}/events",
        json=new_events,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["events"] == new_events["events"]


@pytest.mark.asyncio
async def test_update_eventpush_state(
    client: AsyncClient, sample_eventpushes: list[Eventpush]
):
    """Test updating eventpush state."""
    # Find disabled eventpush
    ep = sample_eventpushes[1]

    response = await client.put(
        f"/api/v2/eventpushes/{ep.id}/state",
        json={"enabled": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_delete_eventpush(
    client: AsyncClient, sample_eventpushes: list[Eventpush]
):
    """Test deleting an eventpush."""
    ep = sample_eventpushes[0]

    response = await client.delete(f"/api/v2/eventpushes/{ep.id}")

    assert response.status_code == 200

    # Verify it's deleted
    response = await client.get("/api/v2/eventpushes")
    data = response.json()
    assert len(data) == len(sample_eventpushes) - 1


@pytest.mark.asyncio
async def test_delete_nonexistent_eventpush(client: AsyncClient):
    """Test deleting non-existent eventpush."""
    response = await client.delete("/api/v2/eventpushes/nonexistent-id")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_nonexistent_eventpush_events(client: AsyncClient):
    """Test updating events for non-existent eventpush."""
    response = await client.put(
        "/api/v2/eventpushes/nonexistent-id/events",
        json={"events": ["test"]},
    )

    assert response.status_code == 404
