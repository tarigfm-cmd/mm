"""Integration tests for organization management endpoints."""
import pytest
from httpx import AsyncClient

# ── Helpers ───────────────────────────────────────────────────────────────────

ADMIN_USER = {
    "email": "orgadmin@example.com",
    "username": "orgadmin",
    "password": "AdminPass1!",
    "full_name": "Org Admin",
}

SECOND_USER = {
    "email": "orgmember@example.com",
    "username": "orgmember",
    "password": "MemberPass1!",
}

ORG_PAYLOAD = {
    "name": "City University Pharmacy",
    "slug": "city-university",
    "org_type": "university",
}


async def register_and_login(client: AsyncClient, user: dict) -> str:
    """Register a user and return their access token."""
    await client.post("/api/auth/register", json=user)
    resp = await client.post("/api/auth/login", json={
        "email": user["email"],
        "password": user["password"],
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_org(client: AsyncClient):
    token = await register_and_login(client, ADMIN_USER)

    resp = await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(token))

    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "city-university"
    assert data["org_type"] == "university"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_org_duplicate_slug(client: AsyncClient):
    token = await register_and_login(client, ADMIN_USER)
    await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(token))

    resp = await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(token))
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_my_orgs_includes_created_org(client: AsyncClient):
    token = await register_and_login(client, ADMIN_USER)
    await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(token))

    resp = await client.get("/api/orgs", headers=auth(token))

    assert resp.status_code == 200
    orgs = resp.json()
    assert any(o["slug"] == "city-university" for o in orgs)
    # Creator should have institution_admin role
    org = next(o for o in orgs if o["slug"] == "city-university")
    assert org["member_role"] == "institution_admin"
    assert org["member_count"] == 1


@pytest.mark.asyncio
async def test_get_org_by_slug(client: AsyncClient):
    token = await register_and_login(client, ADMIN_USER)
    await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(token))

    resp = await client.get("/api/orgs/city-university", headers=auth(token))

    assert resp.status_code == 200
    assert resp.json()["name"] == "City University Pharmacy"


@pytest.mark.asyncio
async def test_get_org_not_member_forbidden(client: AsyncClient):
    admin_token = await register_and_login(client, ADMIN_USER)
    await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(admin_token))

    member_token = await register_and_login(client, SECOND_USER)

    resp = await client.get("/api/orgs/city-university", headers=auth(member_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_roles(client: AsyncClient):
    token = await register_and_login(client, ADMIN_USER)

    resp = await client.get("/api/roles", headers=auth(token))

    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()]
    assert "student" in names
    assert "institution_admin" in names
    assert "platform_admin" in names
    assert len(names) == 6


@pytest.mark.asyncio
async def test_add_member_to_org(client: AsyncClient):
    admin_token = await register_and_login(client, ADMIN_USER)
    await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(admin_token))

    await client.post("/api/auth/register", json=SECOND_USER)

    resp = await client.post(
        "/api/orgs/city-university/members",
        json={"email": SECOND_USER["email"], "role_name": "student"},
        headers=auth(admin_token),
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["role_name"] == "student"
    assert data["email"] == SECOND_USER["email"]


@pytest.mark.asyncio
async def test_add_member_non_admin_forbidden(client: AsyncClient):
    admin_token = await register_and_login(client, ADMIN_USER)
    await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(admin_token))

    member_token = await register_and_login(client, SECOND_USER)
    # Add member as student first
    await client.post(
        "/api/orgs/city-university/members",
        json={"email": SECOND_USER["email"], "role_name": "student"},
        headers=auth(admin_token),
    )

    # Now attempt to add another user from the student account
    third = {"email": "third@example.com", "username": "third", "password": "ThirdPass1!"}
    await client.post("/api/auth/register", json=third)

    resp = await client.post(
        "/api/orgs/city-university/members",
        json={"email": third["email"], "role_name": "student"},
        headers=auth(member_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_members(client: AsyncClient):
    admin_token = await register_and_login(client, ADMIN_USER)
    await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(admin_token))

    await client.post("/api/auth/register", json=SECOND_USER)
    await client.post(
        "/api/orgs/city-university/members",
        json={"email": SECOND_USER["email"], "role_name": "educator"},
        headers=auth(admin_token),
    )

    resp = await client.get("/api/orgs/city-university/members", headers=auth(admin_token))

    assert resp.status_code == 200
    members = resp.json()
    assert len(members) == 2
    emails = [m["email"] for m in members]
    assert ADMIN_USER["email"] in emails
    assert SECOND_USER["email"] in emails


@pytest.mark.asyncio
async def test_update_member_role(client: AsyncClient):
    admin_token = await register_and_login(client, ADMIN_USER)
    await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(admin_token))

    await client.post("/api/auth/register", json=SECOND_USER)
    add_resp = await client.post(
        "/api/orgs/city-university/members",
        json={"email": SECOND_USER["email"], "role_name": "student"},
        headers=auth(admin_token),
    )
    member_id = str(add_resp.json()["user_id"])

    resp = await client.patch(
        f"/api/orgs/city-university/members/{member_id}",
        json={"role_name": "educator"},
        headers=auth(admin_token),
    )

    assert resp.status_code == 200
    assert resp.json()["role_name"] == "educator"


@pytest.mark.asyncio
async def test_remove_member(client: AsyncClient):
    admin_token = await register_and_login(client, ADMIN_USER)
    await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(admin_token))

    await client.post("/api/auth/register", json=SECOND_USER)
    add_resp = await client.post(
        "/api/orgs/city-university/members",
        json={"email": SECOND_USER["email"], "role_name": "student"},
        headers=auth(admin_token),
    )
    member_id = str(add_resp.json()["user_id"])

    resp = await client.delete(
        f"/api/orgs/city-university/members/{member_id}",
        headers=auth(admin_token),
    )
    assert resp.status_code == 204

    # Member should no longer appear in list
    members_resp = await client.get("/api/orgs/city-university/members", headers=auth(admin_token))
    emails = [m["email"] for m in members_resp.json()]
    assert SECOND_USER["email"] not in emails


@pytest.mark.asyncio
async def test_add_duplicate_member_returns_409(client: AsyncClient):
    admin_token = await register_and_login(client, ADMIN_USER)
    await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(admin_token))

    await client.post("/api/auth/register", json=SECOND_USER)
    await client.post(
        "/api/orgs/city-university/members",
        json={"email": SECOND_USER["email"], "role_name": "student"},
        headers=auth(admin_token),
    )

    resp = await client.post(
        "/api/orgs/city-university/members",
        json={"email": SECOND_USER["email"], "role_name": "student"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_add_member_unknown_email_returns_404(client: AsyncClient):
    admin_token = await register_and_login(client, ADMIN_USER)
    await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(admin_token))

    resp = await client.post(
        "/api/orgs/city-university/members",
        json={"email": "ghost@nowhere.com", "role_name": "student"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_org_requires_auth(client: AsyncClient):
    resp = await client.post("/api/orgs", json=ORG_PAYLOAD)
    assert resp.status_code == 403


# ── Organization PATCH (partial update) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_update_org_name_only(client: AsyncClient):
    """PATCH with only name leaves slug and org_type unchanged."""
    token = await register_and_login(client, ADMIN_USER)
    await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(token))

    resp = await client.patch(
        "/api/orgs/city-university",
        json={"name": "Updated University"},
        headers=auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated University"
    assert data["slug"] == "city-university"
    assert data["org_type"] == "university"


@pytest.mark.asyncio
async def test_update_org_slug_only(client: AsyncClient):
    """PATCH with only slug updates the slug without touching other fields."""
    token = await register_and_login(client, ADMIN_USER)
    await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(token))

    resp = await client.patch(
        "/api/orgs/city-university",
        json={"slug": "new-university-slug"},
        headers=auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "new-university-slug"
    assert data["name"] == ORG_PAYLOAD["name"]


@pytest.mark.asyncio
async def test_update_org_requires_admin(client: AsyncClient):
    """Non-admin members cannot PATCH org details."""
    admin_token = await register_and_login(client, ADMIN_USER)
    await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(admin_token))

    member_token = await register_and_login(client, SECOND_USER)
    await client.post(
        "/api/orgs/city-university/members",
        json={"email": SECOND_USER["email"], "role_name": "student"},
        headers=auth(admin_token),
    )

    resp = await client.patch(
        "/api/orgs/city-university",
        json={"name": "Hacked Name"},
        headers=auth(member_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_org_duplicate_slug_returns_409(client: AsyncClient):
    """Changing slug to one already taken returns 409."""
    token = await register_and_login(client, ADMIN_USER)
    await client.post("/api/orgs", json=ORG_PAYLOAD, headers=auth(token))
    await client.post(
        "/api/orgs",
        json={"name": "Other Org", "slug": "other-org", "org_type": "hospital"},
        headers=auth(token),
    )

    resp = await client.patch(
        "/api/orgs/city-university",
        json={"slug": "other-org"},
        headers=auth(token),
    )
    assert resp.status_code == 409


# ── Roles endpoint ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_roles_includes_permissions_field(client: AsyncClient):
    """Each role in the response has a permissions field (list, possibly empty)."""
    token = await register_and_login(client, ADMIN_USER)
    resp = await client.get("/api/roles", headers=auth(token))
    assert resp.status_code == 200
    for role in resp.json():
        assert "permissions" in role
        assert isinstance(role["permissions"], list)
