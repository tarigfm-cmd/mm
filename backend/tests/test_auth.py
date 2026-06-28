"""Integration tests for authentication endpoints."""
import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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

# ── Expired token pruning ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_prunes_revoked_refresh_tokens(client: AsyncClient, fresh_engine):
    """Login removes revoked refresh tokens left over from previous sessions."""
    from datetime import datetime, timedelta, timezone

    from app.core.security import hash_token
    from app.models.identity import RefreshToken, User

    await _register(client)

    # Inject a pre-revoked token directly into the DB to simulate a previous session
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        user_row = (await s.execute(select(User).where(User.email == VALID_USER["email"]))).scalar_one()
        s.add(RefreshToken(
            user_id=user_row.id,
            token_hash=hash_token("stale-revoked-token-value"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            is_revoked=True,
        ))
        await s.commit()

    # Confirm the revoked token is in the DB before login
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        revoked_before = (await s.execute(
            select(func.count(RefreshToken.id)).where(RefreshToken.is_revoked.is_(True))
        )).scalar_one()
    assert revoked_before == 1

    # Login — pruning runs as part of the login handler
    await _login(client)

    # Revoked token must be gone
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        revoked_after = (await s.execute(
            select(func.count(RefreshToken.id)).where(RefreshToken.is_revoked.is_(True))
        )).scalar_one()
    assert revoked_after == 0


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


# ── Password reset ─────────────────────────────────────────────────────────────

def _make_prt(user_id, *, raw_token: str, minutes_until_expiry: int = 60):
    """Build a PasswordResetToken ORM object with a known raw token."""
    from app.core.security import hash_token
    from app.models.identity import PasswordResetToken
    return PasswordResetToken(
        user_id=user_id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=minutes_until_expiry),
    )


@pytest.mark.asyncio
async def test_forgot_password_existing_user_creates_token(
    client: AsyncClient, fresh_engine
) -> None:
    """Forgot-password for an existing user must create a PasswordResetToken record."""
    from app.models.identity import PasswordResetToken, User

    await _register(client)

    resp = await client.post("/api/auth/forgot-password", json={"email": VALID_USER["email"]})
    assert resp.status_code == 200
    assert "password reset" in resp.json()["message"].lower()

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        user = (await s.execute(select(User).where(User.email == VALID_USER["email"]))).scalar_one()
        token_row = (
            await s.execute(
                select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
            )
        ).scalar_one_or_none()

    assert token_row is not None
    assert token_row.used_at is None
    # expires_at may be naive (SQLite) or aware (PostgreSQL); compare naively
    naive_now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires_naive = token_row.expires_at.replace(tzinfo=None) if token_row.expires_at.tzinfo else token_row.expires_at
    assert expires_naive > naive_now


@pytest.mark.asyncio
async def test_forgot_password_nonexistent_user_returns_same_response(
    client: AsyncClient,
) -> None:
    """Forgot-password for unknown email must return the same generic message (no enumeration)."""
    resp_real = await client.post("/api/auth/forgot-password", json={"email": "nobody@nowhere.com"})
    assert resp_real.status_code == 200
    assert "password reset" in resp_real.json()["message"].lower()
    assert resp_real.json().get("reset_url") is None


@pytest.mark.asyncio
async def test_forgot_password_with_dev_flag_returns_reset_url(
    client: AsyncClient,
) -> None:
    """When expose_reset_token_in_dev=True, the reset URL is returned in the response."""
    from unittest.mock import patch
    from app.config import Settings

    await _register(client)

    dev_settings = Settings(expose_reset_token_in_dev=True)
    with patch("app.routes.auth.get_settings", return_value=dev_settings):
        resp = await client.post(
            "/api/auth/forgot-password", json={"email": VALID_USER["email"]}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("reset_url") is not None
    assert "/reset-password?token=" in data["reset_url"]


@pytest.mark.asyncio
async def test_forgot_password_invalidates_previous_unused_tokens(
    client: AsyncClient, fresh_engine
) -> None:
    """A second forgot-password request must invalidate the first token."""
    from app.models.identity import PasswordResetToken, User

    await _register(client)

    await client.post("/api/auth/forgot-password", json={"email": VALID_USER["email"]})
    await client.post("/api/auth/forgot-password", json={"email": VALID_USER["email"]})

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        user = (await s.execute(select(User).where(User.email == VALID_USER["email"]))).scalar_one()
        count = (
            await s.execute(
                select(func.count(PasswordResetToken.id)).where(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.used_at.is_(None),
                )
            )
        ).scalar_one()

    assert count == 1


@pytest.mark.asyncio
async def test_reset_password_valid_token_updates_password(
    client: AsyncClient, fresh_engine
) -> None:
    """Valid token + valid new password must update the user's password."""
    from app.models.identity import User

    await _register(client)

    raw = "ValidResetToken001"
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        user = (await s.execute(select(User).where(User.email == VALID_USER["email"]))).scalar_one()
        s.add(_make_prt(user.id, raw_token=raw))
        await s.commit()

    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": raw, "new_password": "NewPassword1!"},
    )
    assert resp.status_code == 200
    assert "reset" in resp.json()["message"].lower()

    # Can now login with new password
    login = await client.post(
        "/api/auth/login",
        json={"email": VALID_USER["email"], "password": "NewPassword1!"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_expired_token_returns_400(
    client: AsyncClient, fresh_engine
) -> None:
    from app.models.identity import User

    await _register(client)

    raw = "ExpiredResetToken001"
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        user = (await s.execute(select(User).where(User.email == VALID_USER["email"]))).scalar_one()
        s.add(_make_prt(user.id, raw_token=raw, minutes_until_expiry=-1))
        await s.commit()

    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": raw, "new_password": "NewPassword1!"},
    )
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower() or "invalid" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reset_password_already_used_token_returns_400(
    client: AsyncClient, fresh_engine
) -> None:
    from app.models.identity import PasswordResetToken, User

    await _register(client)

    raw = "UsedResetToken001"
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        user = (await s.execute(select(User).where(User.email == VALID_USER["email"]))).scalar_one()
        prt = _make_prt(user.id, raw_token=raw)
        prt.used_at = datetime.now(timezone.utc)
        s.add(prt)
        await s.commit()

    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": raw, "new_password": "NewPassword1!"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_invalid_token_returns_400(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": "nonexistent-token-xyz", "new_password": "NewPassword1!"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_revokes_refresh_tokens(
    client: AsyncClient, fresh_engine
) -> None:
    """After password reset, existing refresh tokens must be revoked."""
    from app.models.identity import RefreshToken, User

    await _register(client)
    tokens = await _login(client)

    raw = "ResetRevokesRT001"
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        user = (await s.execute(select(User).where(User.email == VALID_USER["email"]))).scalar_one()
        s.add(_make_prt(user.id, raw_token=raw))
        await s.commit()

    await client.post(
        "/api/auth/reset-password",
        json={"token": raw, "new_password": "NewPassword1!"},
    )

    # Old refresh token must be revoked
    resp = await client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


# ── Change password ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_change_password_correct_current_password(client: AsyncClient) -> None:
    await _register(client)
    tokens = await _login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": VALID_USER["password"], "new_password": "NewAuthPass2!"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert "changed" in resp.json()["message"].lower()

    # Can login with new password
    login = await client.post(
        "/api/auth/login",
        json={"email": VALID_USER["email"], "password": "NewAuthPass2!"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current_password_returns_400(
    client: AsyncClient,
) -> None:
    await _register(client)
    tokens = await _login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "WrongPassword1!", "new_password": "NewAuthPass2!"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "incorrect" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_change_password_same_as_current_returns_400(client: AsyncClient) -> None:
    await _register(client)
    tokens = await _login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": VALID_USER["password"], "new_password": VALID_USER["password"]},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "different" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_change_password_revokes_refresh_tokens(client: AsyncClient) -> None:
    """After changing password, existing refresh tokens must be revoked."""
    await _register(client)
    tokens = await _login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    await client.post(
        "/api/auth/change-password",
        json={"current_password": VALID_USER["password"], "new_password": "NewAuthPass2!"},
        headers=headers,
    )

    resp = await client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "Anything1!", "new_password": "NewPassword1!"},
    )
    assert resp.status_code in (401, 403)
