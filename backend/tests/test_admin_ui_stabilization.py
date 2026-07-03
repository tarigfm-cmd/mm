"""
Tests for Admin Governance UI Stabilization milestone.

Covers:
- ContentItemListItem includes external_id
- Content list search filter (title and external_id)
- Governance summary endpoint (counts, evidence due, published by region)
- Import batch list/detail endpoints (RBAC + safe metadata)
- Region rules list/create/update endpoints (RBAC enforcement)
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import ContentItem, EvidenceSource, ImportBatch, RegionPublishingRule
from app.models.identity import Organization, OrganizationMembership, Role, User
from app.core.security import hash_password

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_ADMIN = {
    "email": "stab2admin@example.com",
    "username": "stab2admin",
    "password": "StabAdmin2!",
    "full_name": "Stab Admin 2",
}
_REVIEWER = {
    "email": "stab2reviewer@example.com",
    "username": "stab2reviewer",
    "password": "Reviewer2!",
    "full_name": "Stab Reviewer",
}
_IMPORTER = {
    "email": "stab2importer@example.com",
    "username": "stab2importer",
    "password": "Importer2!",
    "full_name": "Stab Importer",
}
_LEARNER = {
    "email": "stab2learner@example.com",
    "username": "stab2learner",
    "password": "Learner2!",
    "full_name": "Stab Learner",
}


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _admin_token(client: AsyncClient, engine) -> str:
    await client.post("/api/auth/register", json=_ADMIN)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        user = (await s.execute(select(User).where(User.email == _ADMIN["email"]))).scalar_one()
        user.is_superuser = True
        await s.commit()
    return await _login(client, _ADMIN["email"], _ADMIN["password"])


async def _role_token(client: AsyncClient, engine, creds: dict, role_name: str) -> str:
    await client.post("/api/auth/register", json=creds)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        user = (await s.execute(select(User).where(User.email == creds["email"]))).scalar_one()
        role = (await s.execute(select(Role).where(Role.name == role_name))).scalar_one()
        org = Organization(
            name=f"org-{role_name}-{creds['username']}",
            slug=f"slug-{role_name[:6]}-{creds['username'][:6]}",
            org_type="university",
        )
        s.add(org)
        await s.flush()
        s.add(OrganizationMembership(user_id=user.id, organization_id=org.id, role_id=role.id))
        await s.commit()
    return await _login(client, creds["email"], creds["password"])


async def _learner_token(client: AsyncClient) -> str:
    await client.post("/api/auth/register", json=_LEARNER)
    return await _login(client, _LEARNER["email"], _LEARNER["password"])


async def _create_item(client: AsyncClient, token: str, external_id: str | None = None) -> dict:
    body: dict = {"title": "Test Case", "content_type": "case"}
    if external_id:
        body["external_id"] = external_id
    resp = await client.post("/api/content/items", json=body, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# 1. external_id in list response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_items_includes_external_id(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    resp = await client.post(
        "/api/content/items",
        json={"title": "BNF Metformin", "content_type": "case", "external_id": "BNF-MET-001"},
        headers=_auth(token),
    )
    assert resp.status_code == 201

    list_resp = await client.get("/api/content/items", headers=_auth(token))
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["external_id"] == "BNF-MET-001"


@pytest.mark.asyncio
async def test_list_items_external_id_null_when_not_set(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    await client.post(
        "/api/content/items",
        json={"title": "No External ID", "content_type": "simulation"},
        headers=_auth(token),
    )
    list_resp = await client.get("/api/content/items", headers=_auth(token))
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert items[0]["external_id"] is None


# ---------------------------------------------------------------------------
# 2. Search filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_by_title(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    await client.post("/api/content/items", json={"title": "Metformin Case", "content_type": "case"}, headers=_auth(token))
    await client.post("/api/content/items", json={"title": "Aspirin Case", "content_type": "case"}, headers=_auth(token))

    resp = await client.get("/api/content/items?search=metformin", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert "Metformin" in data["items"][0]["title"]


@pytest.mark.asyncio
async def test_search_by_external_id(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    await client.post(
        "/api/content/items",
        json={"title": "Drug Case", "content_type": "case", "external_id": "EXT-DRUG-001"},
        headers=_auth(token),
    )
    await client.post(
        "/api/content/items",
        json={"title": "Other Case", "content_type": "case", "external_id": "EXT-OTHER-002"},
        headers=_auth(token),
    )

    resp = await client.get("/api/content/items?search=EXT-DRUG", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["external_id"] == "EXT-DRUG-001"


@pytest.mark.asyncio
async def test_search_returns_empty_on_no_match(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    await client.post("/api/content/items", json={"title": "Some Case", "content_type": "case"}, headers=_auth(token))

    resp = await client.get("/api/content/items?search=zzznomatch", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# 3. Governance summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_governance_summary_requires_content_review(client: AsyncClient, fresh_engine):
    learner_token = await _learner_token(client)
    resp = await client.get("/api/content/governance-summary", headers=_auth(learner_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_governance_summary_empty_db(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    resp = await client.get("/api/content/governance-summary", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_items"] == 0
    assert data["by_status"] == {}
    assert data["by_content_type"] == {}
    assert data["evidence_due_count"] == 0
    assert data["published_by_region"] == {}


@pytest.mark.asyncio
async def test_governance_summary_counts_items(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    await client.post("/api/content/items", json={"title": "Case A", "content_type": "case"}, headers=_auth(token))
    await client.post("/api/content/items", json={"title": "Sim B", "content_type": "simulation"}, headers=_auth(token))

    resp = await client.get("/api/content/governance-summary", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_items"] == 2
    assert data["by_content_type"].get("case") == 1
    assert data["by_content_type"].get("simulation") == 1


@pytest.mark.asyncio
async def test_governance_summary_evidence_due_count(client: AsyncClient, fresh_engine):
    from datetime import datetime, timezone, timedelta

    token = await _admin_token(client, fresh_engine)
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()

    # Create evidence via API
    base_body = {
        "title": "BNF Monograph",
        "evidence_status": "active",
        "next_review_due_at": past,
    }
    await client.post("/api/evidence/sources", json=base_body, headers=_auth(token))

    not_due_body = {
        "title": "NICE Guideline",
        "evidence_status": "active",
        "next_review_due_at": future,
    }
    await client.post("/api/evidence/sources", json=not_due_body, headers=_auth(token))

    resp = await client.get("/api/content/governance-summary", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["evidence_due_count"] == 1


@pytest.mark.asyncio
async def test_governance_summary_accessible_to_reviewer(client: AsyncClient, fresh_engine):
    reviewer_token = await _role_token(client, fresh_engine, _REVIEWER, "content_reviewer")
    resp = await client.get("/api/content/governance-summary", headers=_auth(reviewer_token))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 4. Import batches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_batches_list_requires_permission(client: AsyncClient, fresh_engine):
    learner_token = await _learner_token(client)
    resp = await client.get("/api/content/import/batches", headers=_auth(learner_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_import_batches_list_empty(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    resp = await client.get("/api/content/import/batches", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_import_batches_list_returns_metadata(client: AsyncClient, fresh_engine):
    from datetime import datetime, timezone

    token = await _admin_token(client, fresh_engine)

    # Seed an ImportBatch directly
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        batch = ImportBatch(
            source_file_name="test.csv",
            package_type="csv",
            status="committed",
            total_rows=100,
            valid_rows=99,
            invalid_rows=1,
            created_items=99,
            created_versions=99,
            created_evidence_sources=0,
            created_region_rules=0,
            skipped_duplicates=0,
            committed_at=datetime.now(timezone.utc),
        )
        s.add(batch)
        await s.commit()
        batch_id = str(batch.id)

    resp = await client.get("/api/content/import/batches", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["id"] == batch_id
    assert item["source_file_name"] == "test.csv"
    assert item["package_type"] == "csv"
    assert item["status"] == "committed"
    assert item["total_rows"] == 100
    assert item["created_items"] == 99
    # Raw clinical payload must not appear; warnings_json is admin metadata and is allowed
    assert "payload_json" not in item
    assert "errors_json" not in item


@pytest.mark.asyncio
async def test_import_batch_detail_not_found(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    resp = await client.get(f"/api/content/import/batches/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_import_batch_detail_returns_metadata(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        batch = ImportBatch(
            source_file_name="detail_test.zip",
            package_type="zip",
            status="committed",
            total_rows=50,
            valid_rows=50,
            invalid_rows=0,
            created_items=50,
            created_versions=50,
            created_evidence_sources=2,
            created_region_rules=1,
            skipped_duplicates=0,
        )
        s.add(batch)
        await s.commit()
        batch_id = str(batch.id)

    resp = await client.get(f"/api/content/import/batches/{batch_id}", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == batch_id
    assert data["source_file_name"] == "detail_test.zip"
    assert data["created_evidence_sources"] == 2


@pytest.mark.asyncio
async def test_import_batches_accessible_to_importer_role(client: AsyncClient, fresh_engine):
    importer_token = await _role_token(client, fresh_engine, _IMPORTER, "educator")
    resp = await client.get("/api/content/import/batches", headers=_auth(importer_token))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 5. Region rules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_region_rules_list_requires_content_review(client: AsyncClient, fresh_engine):
    learner_token = await _learner_token(client)
    resp = await client.get("/api/content/region-rules", headers=_auth(learner_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_region_rules_list_empty(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    resp = await client.get("/api/content/region-rules", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_region_rule_create_requires_content_publish(client: AsyncClient, fresh_engine):
    reviewer_token = await _role_token(client, fresh_engine, _REVIEWER, "content_reviewer")
    resp = await client.post(
        "/api/content/region-rules",
        json={"region_code": "UK", "is_active": True},
        headers=_auth(reviewer_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_region_rule_create_success(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    resp = await client.post(
        "/api/content/region-rules",
        json={
            "region_code": "UK",
            "content_type": "case",
            "allowed_statuses": ["clinically_approved"],
            "is_active": True,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["region_code"] == "UK"
    assert data["content_type"] == "case"
    assert data["allowed_statuses"] == ["clinically_approved"]
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_region_rule_create_invalid_region_rejected(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    resp = await client.post(
        "/api/content/region-rules",
        json={"region_code": "INVALID", "is_active": True},
        headers=_auth(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_region_rule_update_success(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)

    create_resp = await client.post(
        "/api/content/region-rules",
        json={"region_code": "US", "is_active": True},
        headers=_auth(token),
    )
    assert create_resp.status_code == 201
    rule_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/api/content/region-rules/{rule_id}",
        json={"is_active": False, "allowed_statuses": ["clinically_approved", "published"]},
        headers=_auth(token),
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["is_active"] is False
    assert "clinically_approved" in data["allowed_statuses"]


@pytest.mark.asyncio
async def test_region_rule_update_requires_content_publish(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    create_resp = await client.post(
        "/api/content/region-rules",
        json={"region_code": "GCC", "is_active": True},
        headers=_auth(token),
    )
    rule_id = create_resp.json()["id"]

    reviewer_token = await _role_token(client, fresh_engine, _REVIEWER, "content_reviewer")
    resp = await client.patch(
        f"/api/content/region-rules/{rule_id}",
        json={"is_active": False},
        headers=_auth(reviewer_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_region_rule_update_not_found(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    resp = await client.patch(
        f"/api/content/region-rules/{uuid.uuid4()}",
        json={"is_active": False},
        headers=_auth(token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_region_rules_list_filter_by_region(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    await client.post("/api/content/region-rules", json={"region_code": "UK", "is_active": True}, headers=_auth(token))
    await client.post("/api/content/region-rules", json={"region_code": "US", "is_active": True}, headers=_auth(token))

    resp = await client.get("/api/content/region-rules?region_code=UK", headers=_auth(token))
    assert resp.status_code == 200
    rules = resp.json()
    assert len(rules) == 1
    assert rules[0]["region_code"] == "UK"


@pytest.mark.asyncio
async def test_region_rules_accessible_to_reviewer(client: AsyncClient, fresh_engine):
    reviewer_token = await _role_token(client, fresh_engine, _REVIEWER, "content_reviewer")
    resp = await client.get("/api/content/region-rules", headers=_auth(reviewer_token))
    assert resp.status_code == 200
