"""Integration tests for authentication endpoints."""
import pytest
from httpx import AsyncClient

VALID_USER = {
    "email": "authtest@example.com",
    "username": "authtest",
    "password": "AuthPass1!",
    "full_name": "Auth Tester",
}


async def _register(client: AsyncClient, user: dict = VALID_USER) -> dict:
    resp = await client.post("/api/auth/register", json=user)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _login(client: AsyncClient, user: dict = VALID_USER) -> dict:
    resp = await client.post("/api/auth/login", json={
        "email": user["email"],
        "password": user["password"],
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Registration ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_returns_201_with_user(client: AsyncClient):
    data = await _register(client)
    assert data["email"] == VALID_USER["email"]
    assert data["username"] == VALID_USER["username"]
    assert data["full_name"] == VALID_USER["full_name"]
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client: AsyncClient):
    await _register(client)
    resp = await client.post("/api/auth/register", json={
        **VALID_USER,
        "username": "different",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_duplicate_username_returns_409(client: AsyncClient):
    await _register(client)
    resp = await client.post("/api/auth/register", json={
        **VALID_USER,
        "email": "other@example.com",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password_rejected(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={
        **VALID_USER,
        "password": "weakpassword",
    })
    assert resp.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_returns_tokens(client: AsyncClient):
    await _register(client)
    tokens = await _login(client)
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient):
    await _register(client)
    resp = await client.post("/api/auth/login", json={
        "email": VALID_USER["email"],
        "password": "WrongPass1!",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(client: AsyncClient):
    resp = await client.post("/api/auth/login", json={
        "email": "nobody@example.com",
        "password": "AnyPass1!",
    })
    assert resp.status_code == 401


# ── Token refresh ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_returns_new_tokens(client: AsyncClient):
    await _register(client)
    tokens = await _login(client)

    resp = await client.post("/api/auth/refresh", json={
        "refresh_token": tokens["refresh_token"],
    })
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    # Token rotation: new refresh token must differ from old one
    assert new_tokens["refresh_token"] != tokens["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_token_rotation_prevents_reuse(client: AsyncClient):
    """After rotation, the old refresh token must be rejected."""
    await _register(client)
    tokens = await _login(client)
    old_rt = tokens["refresh_token"]

    # Consume the refresh token
    resp = await client.post("/api/auth/refresh", json={"refresh_token": old_rt})
    assert resp.status_code == 200

    # Attempt to reuse the old token — must be rejected
    resp2 = await client.post("/api/auth/refresh", json={"refresh_token": old_rt})
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_refresh_invalid_token_returns_401(client: AsyncClient):
    resp = await client.post("/api/auth/refresh", json={"refresh_token": "not.a.token"})
    assert resp.status_code == 401


# ── Current user ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_me_returns_user_profile(client: AsyncClient):
    await _register(client)
    tokens = await _login(client)

    resp = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == VALID_USER["email"]
    assert data["username"] == VALID_USER["username"]


@pytest.mark.asyncio
async def test_me_without_token_returns_403(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_me_with_invalid_token_returns_401(client: AsyncClient):
    resp = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp.status_code == 401


# ── Profile update ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_profile_full_name(client: AsyncClient):
    await _register(client)
    tokens = await _login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await client.patch(
        "/api/auth/me",
        json={"full_name": "Updated Name"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_username_conflict_returns_409(client: AsyncClient):
    # Register two users
    await _register(client)
    other = {
        "email": "other@example.com",
        "username": "otherauthtest",
        "password": "OtherPass1!",
    }
    await client.post("/api/auth/register", json=other)
    tokens = await _login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await client.patch(
        "/api/auth/me",
        json={"username": "otherauthtest"},
        headers=headers,
    )
    assert resp.status_code == 409


# ── Logout ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client: AsyncClient):
    await _register(client)
    tokens = await _login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await client.post(
        "/api/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )
    assert resp.status_code == 204

    # After logout, the refresh token must be rejected
    resp2 = await client.post("/api/auth/refresh", json={
        "refresh_token": tokens["refresh_token"],
    })
    assert resp2.status_code == 401
