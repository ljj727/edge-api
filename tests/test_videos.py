"""Tests for video endpoints."""

import pytest
from httpx import AsyncClient

from app.models.video import Video


@pytest.mark.asyncio
async def test_get_videos(
    client: AsyncClient, sample_videos: list[Video], auth_headers: dict
):
    """Test getting all videos."""
    response = await client.get("/api/v2/videos", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(sample_videos)


@pytest.mark.asyncio
async def test_get_videos_unauthorized(client: AsyncClient):
    """Test getting videos without auth."""
    response = await client.get("/api/v2/videos")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_video(client: AsyncClient, auth_headers: dict):
    """Test creating a new video."""
    video_data = {
        "uri": "rtsp://192.168.1.200:554/stream1",
        "name": "New Camera",
        "deviceId": "cam-new",
        "serverId": "server-001",
        "settings": {
            "maskingRegion": [],
            "detectionPoint": "c:b",
            "lineCrossPoint": "c:c",
        },
    }

    response = await client.post(
        "/api/v2/videos",
        json=video_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["uri"] == video_data["uri"]
    assert data["name"] == video_data["name"]
    assert data["deviceId"] == video_data["deviceId"]


@pytest.mark.asyncio
async def test_create_video_minimal(client: AsyncClient, auth_headers: dict):
    """Test creating a video with minimal data."""
    video_data = {"uri": "rtsp://192.168.1.200:554/stream1"}

    response = await client.post(
        "/api/v2/videos",
        json=video_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["uri"] == video_data["uri"]
    assert "id" in data


@pytest.mark.asyncio
async def test_update_video_settings(
    client: AsyncClient, sample_videos: list[Video], auth_headers: dict
):
    """Test updating video settings."""
    video_id = sample_videos[0].id
    new_settings = {
        "settings": {
            "maskingRegion": [[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]],
            "detectionPoint": "c:c",
            "lineCrossPoint": "c:b",
        }
    }

    response = await client.put(
        f"/api/v2/videos/{video_id}/video-setting",
        json=new_settings,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["settings"]["detectionPoint"] == "c:c"


@pytest.mark.asyncio
async def test_delete_video(
    client: AsyncClient, sample_videos: list[Video], auth_headers: dict
):
    """Test deleting a video."""
    video_id = sample_videos[0].id

    response = await client.delete(
        f"/api/v2/videos/{video_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200

    # Verify video is deleted
    response = await client.get("/api/v2/videos", headers=auth_headers)
    data = response.json()
    assert len(data) == len(sample_videos) - 1


@pytest.mark.asyncio
async def test_delete_nonexistent_video(client: AsyncClient, auth_headers: dict):
    """Test deleting a non-existent video."""
    response = await client.delete(
        "/api/v2/videos/nonexistent-id",
        headers=auth_headers,
    )

    assert response.status_code == 404
