"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, admin_user: User):
    """Test successful login."""
    response = await client.post(
        "/api/v2/auth",
        json={"id": "admin", "password": "admin"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert len(data["token"]) > 0


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, admin_user: User):
    """Test login with wrong password."""
    response = await client.post(
        "/api/v2/auth",
        json={"id": "admin", "password": "wrongpassword"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Test login with non-existent user."""
    response = await client.post(
        "/api/v2/auth",
        json={"id": "nonexistent", "password": "password"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_missing_fields(client: AsyncClient):
    """Test login with missing fields."""
    response = await client.post(
        "/api/v2/auth",
        json={"id": "admin"},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_change_password(
    client: AsyncClient, test_user: User, auth_headers: dict
):
    """Test password change."""
    response = await client.put(
        f"/api/v2/users/{test_user.id}/password",
        json={"password": "newpassword123"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_change_password_unauthorized(client: AsyncClient, test_user: User):
    """Test password change without auth."""
    response = await client.put(
        f"/api/v2/users/{test_user.id}/password",
        json={"password": "newpassword123"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_change_other_user_password(
    client: AsyncClient, admin_user: User, auth_headers: dict
):
    """Test changing another user's password (should fail for non-admin)."""
    response = await client.put(
        f"/api/v2/users/{admin_user.id}/password",
        json={"password": "newpassword123"},
        headers=auth_headers,
    )

    assert response.status_code == 403
