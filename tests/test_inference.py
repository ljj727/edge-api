"""Tests for inference endpoints."""

import pytest
from httpx import AsyncClient

from app.models.inference import Inference
from app.models.video import Video


@pytest.mark.asyncio
async def test_get_inferences(
    client: AsyncClient,
    sample_inferences: list[Inference],
    sample_videos: list[Video],
    auth_headers: dict,
):
    """Test getting inferences."""
    response = await client.get(
        "/api/v2/inference",
        params={"videoId": sample_videos[0].id},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_inferences_unauthorized(client: AsyncClient):
    """Test getting inferences without auth."""
    response = await client.get("/api/v2/inference")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_inference(
    client: AsyncClient, sample_videos: list[Video], auth_headers: dict
):
    """Test creating an inference."""
    inference_data = {
        "appId": "app-test-detection",
        "videoId": sample_videos[1].id,
        "uri": "http://localhost:8080/v1/inference",
        "name": "Test Inference",
        "type": "detection",
        "settings": {
            "version": "1.6.1",
            "configs": [
                {
                    "eventType": "intrusion",
                    "eventSettingId": "event-test",
                    "eventSettingName": "Test Zone",
                    "points": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
                }
            ],
        },
    }

    response = await client.post(
        "/api/v2/inference",
        json=inference_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["appId"] == inference_data["appId"]
    assert data["videoId"] == inference_data["videoId"]


@pytest.mark.asyncio
async def test_delete_inference(
    client: AsyncClient,
    sample_inferences: list[Inference],
    auth_headers: dict,
):
    """Test deleting an inference."""
    inf = sample_inferences[0]

    response = await client.delete(
        "/api/v2/inference",
        params={"appId": inf.app_id, "videoId": inf.video_id},
        headers=auth_headers,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_nonexistent_inference(client: AsyncClient, auth_headers: dict):
    """Test deleting non-existent inference."""
    response = await client.delete(
        "/api/v2/inference",
        params={"appId": "nonexistent", "videoId": "nonexistent"},
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_event_setting(
    client: AsyncClient,
    sample_inferences: list[Inference],
    auth_headers: dict,
):
    """Test updating inference event settings."""
    inf = sample_inferences[0]

    new_settings = {
        "settings": {
            "version": "1.6.2",
            "configs": [
                {
                    "eventType": "loitering",
                    "eventSettingId": "event-updated",
                    "eventSettingName": "Updated Zone",
                    "points": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
                    "timeout": 30,
                }
            ],
        }
    }

    response = await client.put(
        "/api/v2/inference/event-setting",
        params={"appId": inf.app_id, "videoId": inf.video_id},
        json=new_settings,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["settings"]["version"] == "1.6.2"


@pytest.mark.asyncio
async def test_get_inference_status(
    client: AsyncClient,
    sample_inferences: list[Inference],
    sample_videos: list[Video],
    auth_headers: dict,
):
    """Test getting inference status."""
    response = await client.get(
        "/api/v2/inference/status",
        params={"videoId": sample_videos[0].id},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
