"""Integration tests — verify AuditLog records are written for key actions."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import AuditLog

_USER = {
    "email": "audit@example.com",
    "username": "audituser",
    "password": "AuditPass1!",
}
_OTHER = {
    "email": "auditother@example.com",
    "username": "auditother",
    "password": "OtherPass1!",
}
_ORG = {"name": "Audit Org", "slug": "audit-org", "org_type": "university"}


async def _logs(engine, action: str) -> list:
    async with AsyncSession(engine, expire_on_commit=False) as s:
        result = await s.execute(select(AuditLog).where(AuditLog.action == action))
        return result.scalars().all()


async def _register_login(client: AsyncClient, user: dict = _USER) -> dict:
    await client.post("/api/auth/register", json=user)
    resp = await client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    return resp.json()


# ── Auth actions ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_writes_audit_log(client: AsyncClient, fresh_engine):
    await client.post("/api/auth/register", json=_USER)
    logs = await _logs(fresh_engine, "user.register")
    assert len(logs) == 1
    assert logs[0].resource_type == "user"
    assert logs[0].extra_data is not None
    assert logs[0].extra_data.get("email") == _USER["email"]


@pytest.mark.asyncio
async def test_login_writes_audit_log(client: AsyncClient, fresh_engine):
    await _register_login(client)
    logs = await _logs(fresh_engine, "user.login")
    assert len(logs) == 1
    assert logs[0].resource_type == "user"


@pytest.mark.asyncio
async def test_logout_writes_audit_log(client: AsyncClient, fresh_engine):
    tokens = await _register_login(client)
    await client.post(
        "/api/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    logs = await _logs(fresh_engine, "user.logout")
    assert len(logs) == 1


@pytest.mark.asyncio
async def test_token_refresh_writes_audit_log(client: AsyncClient, fresh_engine):
    tokens = await _register_login(client)
    await client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    logs = await _logs(fresh_engine, "auth.token_refresh")
    assert len(logs) == 1


# ── Organization actions ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_org_create_writes_audit_log(client: AsyncClient, fresh_engine):
    tokens = await _register_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.post("/api/orgs", json=_ORG, headers=headers)
    logs = await _logs(fresh_engine, "org.create")
    assert len(logs) == 1
    assert logs[0].resource_type == "organization"
    assert logs[0].extra_data.get("slug") == "audit-org"


@pytest.mark.asyncio
async def test_org_update_writes_audit_log(client: AsyncClient, fresh_engine):
    tokens = await _register_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.post("/api/orgs", json=_ORG, headers=headers)
    await client.patch("/api/orgs/audit-org", json={"name": "Updated Org"}, headers=headers)
    logs = await _logs(fresh_engine, "org.update")
    assert len(logs) == 1


@pytest.mark.asyncio
async def test_member_added_writes_audit_log(client: AsyncClient, fresh_engine):
    tokens = await _register_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.post("/api/orgs", json=_ORG, headers=headers)
    await client.post("/api/auth/register", json=_OTHER)
    await client.post(
        "/api/orgs/audit-org/members",
        json={"email": _OTHER["email"], "role_name": "student"},
        headers=headers,
    )
    logs = await _logs(fresh_engine, "org.member_added")
    assert len(logs) == 1
    assert logs[0].extra_data.get("role") == "student"


@pytest.mark.asyncio
async def test_member_role_updated_writes_audit_log(client: AsyncClient, fresh_engine):
    tokens = await _register_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.post("/api/orgs", json=_ORG, headers=headers)
    await client.post("/api/auth/register", json=_OTHER)
    add_resp = await client.post(
        "/api/orgs/audit-org/members",
        json={"email": _OTHER["email"], "role_name": "student"},
        headers=headers,
    )
    member_id = add_resp.json()["user_id"]
    await client.patch(
        f"/api/orgs/audit-org/members/{member_id}",
        json={"role_name": "educator"},
        headers=headers,
    )
    logs = await _logs(fresh_engine, "org.member_role_updated")
    assert len(logs) == 1
    assert logs[0].extra_data.get("new_role") == "educator"
    assert logs[0].extra_data.get("old_role") == "student"


@pytest.mark.asyncio
async def test_member_removed_writes_audit_log(client: AsyncClient, fresh_engine):
    tokens = await _register_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.post("/api/orgs", json=_ORG, headers=headers)
    await client.post("/api/auth/register", json=_OTHER)
    add_resp = await client.post(
        "/api/orgs/audit-org/members",
        json={"email": _OTHER["email"], "role_name": "student"},
        headers=headers,
    )
    member_id = add_resp.json()["user_id"]
    await client.delete(f"/api/orgs/audit-org/members/{member_id}", headers=headers)
    logs = await _logs(fresh_engine, "org.member_removed")
    assert len(logs) == 1


# ── Safety: no secrets in log records ────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_password_or_raw_token_in_audit_records(client: AsyncClient, fresh_engine):
    tokens = await _register_login(client)
    await client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        all_logs = (await s.execute(select(AuditLog))).scalars().all()

    for log in all_logs:
        serialized = str(log.extra_data or "")
        assert "password" not in serialized.lower()
        assert "hashed_password" not in serialized.lower()
