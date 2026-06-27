"""
Integration tests for the content governance API.

All tests use a per-test isolated in-memory SQLite database via the
`client` and `fresh_engine` fixtures from conftest.py.
"""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import (
    ContentItem,
    ContentVersion,
    ClinicalReview,
    EvidenceSource,
    LearnerFailureAnalytics,
    PublicationRecord,
)
from app.models.identity import AuditLog, User
from app.core.security import hash_password

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUPERUSER = {
    "email": "admin@example.com",
    "username": "superadmin",
    "password": "AdminPass1!",
    "full_name": "Super Admin",
}

_REGULAR_USER = {
    "email": "learner@example.com",
    "username": "learner01",
    "password": "LearnerPass1!",
    "full_name": "Learner One",
}


async def _make_superuser(engine) -> None:
    """Promote the registered superuser account to is_superuser=True."""
    async with AsyncSession(engine, expire_on_commit=False) as s:
        result = await s.execute(select(User).where(User.email == _SUPERUSER["email"]))
        user = result.scalar_one()
        user.is_superuser = True
        await s.commit()


async def _register_and_login(client: AsyncClient, creds: dict) -> str:
    """Register user and return access token."""
    await client.post("/api/auth/register", json=creds)
    resp = await client.post(
        "/api/auth/login",
        json={"email": creds["email"], "password": creds["password"]},
    )
    return resp.json()["access_token"]


async def _admin_token(client: AsyncClient, engine) -> str:
    token = await _register_and_login(client, _SUPERUSER)
    await _make_superuser(engine)
    # Re-login to get token for the now-superuser account
    resp = await client.post(
        "/api/auth/login",
        json={"email": _SUPERUSER["email"], "password": _SUPERUSER["password"]},
    )
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _item_payload(**kwargs) -> dict:
    base = {
        "title": "Aspirin OTC Case",
        "content_type": "case",
        "domain": "OTC",
        "specialty": "analgesics",
        "difficulty": "beginner",
        "region_scope": ["UK"],
    }
    base.update(kwargs)
    return base


async def _create_item(client: AsyncClient, token: str, **kwargs) -> dict:
    resp = await client.post("/api/content/items", json=_item_payload(**kwargs), headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_version(client: AsyncClient, token: str, item_id: str, **kwargs) -> dict:
    payload = {"payload_json": {"q": "What is the max daily dose of aspirin?"}, "change_summary": "Initial version"}
    payload.update(kwargs)
    resp = await client.post(f"/api/content/items/{item_id}/versions", json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_review(client: AsyncClient, token: str, item_id: str, decision: str = "approved") -> dict:
    resp = await client.post(
        f"/api/content/items/{item_id}/reviews",
        json={"review_decision": decision, "clinical_accuracy_score": 0.95, "safety_score": 0.98},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _publish(client: AsyncClient, token: str, item_id: str, region: str = "UK") -> dict:
    resp = await client.post(
        f"/api/content/items/{item_id}/publish",
        json={"region_code": region, "reason": "Ready for learners"},
        headers=_auth(token),
    )
    return resp.json(), resp.status_code


# ---------------------------------------------------------------------------
# Content Item CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_content_item_requires_superuser(client: AsyncClient, fresh_engine):
    learner_token = await _register_and_login(client, _REGULAR_USER)
    resp = await client.post("/api/content/items", json=_item_payload(), headers=_auth(learner_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_content_item_success(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    assert item["title"] == "Aspirin OTC Case"
    assert item["content_type"] == "case"
    assert item["status"] == "draft"
    assert item["region_scope"] == ["UK"]


@pytest.mark.asyncio
async def test_create_content_item_invalid_type_rejected(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    resp = await client.post("/api/content/items", json=_item_payload(content_type="invalid_type"), headers=_auth(token))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_content_item_writes_audit_log(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    await _create_item(client, token)
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        result = await s.execute(select(AuditLog).where(AuditLog.action == "content.item_created"))
        logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].resource_type == "content_item"


@pytest.mark.asyncio
async def test_get_content_item_not_found(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    resp = await client.get(f"/api/content/items/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_learner_cannot_see_draft_item(client: AsyncClient, fresh_engine):
    admin_token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, admin_token)

    learner_token = await _register_and_login(client, _REGULAR_USER)
    resp = await client.get(f"/api/content/items/{item['id']}", headers=_auth(learner_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_items_learner_sees_only_published(client: AsyncClient, fresh_engine):
    admin_token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, admin_token)
    await _create_version(client, admin_token, item["id"])
    await _create_review(client, admin_token, item["id"])
    pub, status_code = await _publish(client, admin_token, item["id"])
    assert status_code == 201

    learner_token = await _register_and_login(client, _REGULAR_USER)
    resp = await client.get("/api/content/items", headers=_auth(learner_token))
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert item["id"] in ids


# ---------------------------------------------------------------------------
# Content Versions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_version_increments_number(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)

    v1 = await _create_version(client, token, item["id"])
    assert v1["version_number"] == 1
    assert v1["is_current"] is True

    v2 = await _create_version(client, token, item["id"], change_summary="Updated dose info")
    assert v2["version_number"] == 2
    assert v2["is_current"] is True


@pytest.mark.asyncio
async def test_create_version_updates_item_current_version(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    v1 = await _create_version(client, token, item["id"])

    # Re-fetch the item
    resp = await client.get(f"/api/content/items/{item['id']}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["current_version_id"] == v1["id"]


@pytest.mark.asyncio
async def test_create_version_writes_audit_log(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    await _create_version(client, token, item["id"])

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        result = await s.execute(select(AuditLog).where(AuditLog.action == "content.version_created"))
        logs = result.scalars().all()
    assert len(logs) == 1


@pytest.mark.asyncio
async def test_rollback_version_creates_new_copy(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    v1 = await _create_version(client, token, item["id"])
    await _create_version(client, token, item["id"], change_summary="Breaking change")

    resp = await client.post(
        f"/api/content/items/{item['id']}/versions/rollback/{v1['id']}",
        headers=_auth(token),
    )
    assert resp.status_code == 201
    rollback = resp.json()
    assert rollback["version_number"] == 3
    assert rollback["is_current"] is True
    assert "Rollback" in rollback["change_summary"]


@pytest.mark.asyncio
async def test_rollback_writes_audit_log(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    v1 = await _create_version(client, token, item["id"])
    await _create_version(client, token, item["id"])

    await client.post(
        f"/api/content/items/{item['id']}/versions/rollback/{v1['id']}",
        headers=_auth(token),
    )
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        result = await s.execute(select(AuditLog).where(AuditLog.action == "content.version_rollback"))
        logs = result.scalars().all()
    assert len(logs) == 1


# ---------------------------------------------------------------------------
# Clinical Reviews
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_review_success(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    review = await _create_review(client, token, item["id"])
    assert review["review_decision"] == "approved"
    assert review["content_item_id"] == item["id"]
    assert review["clinical_accuracy_score"] == 0.95


@pytest.mark.asyncio
async def test_create_review_invalid_decision_rejected(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    resp = await client.post(
        f"/api/content/items/{item['id']}/reviews",
        json={"review_decision": "thumbs_up"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_review_writes_audit_log(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    await _create_review(client, token, item["id"])

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        result = await s.execute(select(AuditLog).where(AuditLog.action == "content.review_created"))
        logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].extra_data["review_decision"] == "approved"


@pytest.mark.asyncio
async def test_list_reviews_for_item(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    await _create_review(client, token, item["id"])
    await _create_review(client, token, item["id"], decision="needs_revision")

    resp = await client.get(f"/api/content/items/{item['id']}/reviews", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_requires_version(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    # No version added
    pub, status_code = await _publish(client, token, item["id"])
    assert status_code == 409


@pytest.mark.asyncio
async def test_publish_requires_approved_review(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    await _create_version(client, token, item["id"])
    # No review added
    pub, status_code = await _publish(client, token, item["id"])
    assert status_code == 409


@pytest.mark.asyncio
async def test_publish_success_sets_status_published(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    await _create_version(client, token, item["id"])
    await _create_review(client, token, item["id"])
    pub, status_code = await _publish(client, token, item["id"])
    assert status_code == 201
    assert pub["publication_status"] == "published"
    assert pub["region_code"] == "UK"

    # Item status updated
    resp = await client.get(f"/api/content/items/{item['id']}", headers=_auth(token))
    assert resp.json()["status"] == "published"


@pytest.mark.asyncio
async def test_publish_writes_audit_log(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    await _create_version(client, token, item["id"])
    await _create_review(client, token, item["id"])
    await _publish(client, token, item["id"])

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        result = await s.execute(select(AuditLog).where(AuditLog.action == "content.published"))
        logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].extra_data["region_code"] == "UK"


@pytest.mark.asyncio
async def test_unpublish_success(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    await _create_version(client, token, item["id"])
    await _create_review(client, token, item["id"])
    await _publish(client, token, item["id"])

    resp = await client.post(
        f"/api/content/items/{item['id']}/unpublish",
        json={"region_code": "UK", "reason": "Needs updated evidence"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["publication_status"] == "unpublished"


@pytest.mark.asyncio
async def test_unpublish_writes_audit_log(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    await _create_version(client, token, item["id"])
    await _create_review(client, token, item["id"])
    await _publish(client, token, item["id"])
    await client.post(
        f"/api/content/items/{item['id']}/unpublish",
        json={"region_code": "UK"},
        headers=_auth(token),
    )

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        result = await s.execute(select(AuditLog).where(AuditLog.action == "content.unpublished"))
        logs = result.scalars().all()
    assert len(logs) == 1


@pytest.mark.asyncio
async def test_list_published_by_region(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    await _create_version(client, token, item["id"])
    await _create_review(client, token, item["id"])
    await _publish(client, token, item["id"], region="UK")

    # UK region — should see the item
    resp = await client.get("/api/content/published?region=UK", headers=_auth(token))
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert item["id"] in ids

    # US region — should NOT see the item
    resp = await client.get("/api/content/published?region=US", headers=_auth(token))
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert item["id"] not in ids


# ---------------------------------------------------------------------------
# Approval Batches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_approval_batch_success(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    resp = await client.post(
        "/api/content/approval-batches",
        json={
            "batch_name": "Batch 1",
            "approved_by_team_name": "UKCPA Pharmacists",
            "approved_at": "2026-01-15T10:00:00Z",
            "region_scope": ["UK"],
            "content_count": 50,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["batch_name"] == "Batch 1"
    assert data["approved_by_team_name"] == "UKCPA Pharmacists"


@pytest.mark.asyncio
async def test_create_approval_batch_writes_audit_log(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    await client.post(
        "/api/content/approval-batches",
        json={
            "batch_name": "Batch 2",
            "approved_by_team_name": "UKCPA Pharmacists",
            "approved_at": "2026-01-15T10:00:00Z",
        },
        headers=_auth(token),
    )
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        result = await s.execute(
            select(AuditLog).where(AuditLog.action == "content.approval_batch_created")
        )
        logs = result.scalars().all()
    assert len(logs) == 1


# ---------------------------------------------------------------------------
# Evidence Sources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_evidence_source_success(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    resp = await client.post(
        "/api/evidence/sources",
        json={
            "title": "NICE CG87 — Hypertension",
            "organization": "NICE",
            "source_type": "guideline",
            "region": "UK",
            "evidence_status": "active",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "NICE CG87 — Hypertension"
    assert resp.json()["region"] == "UK"


@pytest.mark.asyncio
async def test_create_evidence_source_invalid_region_rejected(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    resp = await client.post(
        "/api/evidence/sources",
        json={"title": "Test", "region": "INVALID", "evidence_status": "active"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_evidence_source_partial(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    create_resp = await client.post(
        "/api/evidence/sources",
        json={"title": "BNF Chapter 2", "evidence_status": "active"},
        headers=_auth(token),
    )
    source_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/evidence/sources/{source_id}",
        json={"evidence_status": "needs_review", "notes": "Due for annual review"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["evidence_status"] == "needs_review"
    assert resp.json()["notes"] == "Due for annual review"


@pytest.mark.asyncio
async def test_update_evidence_source_writes_audit_log(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    create_resp = await client.post(
        "/api/evidence/sources",
        json={"title": "Audit Evidence", "evidence_status": "active"},
        headers=_auth(token),
    )
    source_id = create_resp.json()["id"]
    await client.patch(
        f"/api/evidence/sources/{source_id}",
        json={"evidence_status": "superseded"},
        headers=_auth(token),
    )

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        result = await s.execute(
            select(AuditLog).where(AuditLog.action == "content.evidence_source_updated")
        )
        logs = result.scalars().all()
    assert len(logs) == 1


@pytest.mark.asyncio
async def test_list_due_for_review(client: AsyncClient, fresh_engine):
    token = await _admin_token(client, fresh_engine)
    past = "2020-01-01T00:00:00Z"
    future = "2030-01-01T00:00:00Z"

    await client.post(
        "/api/evidence/sources",
        json={"title": "Overdue Source", "evidence_status": "active", "next_review_due_at": past},
        headers=_auth(token),
    )
    await client.post(
        "/api/evidence/sources",
        json={"title": "Future Source", "evidence_status": "active", "next_review_due_at": future},
        headers=_auth(token),
    )

    resp = await client.get("/api/evidence/due-for-review", headers=_auth(token))
    assert resp.status_code == 200
    titles = [s["title"] for s in resp.json()]
    assert "Overdue Source" in titles
    assert "Future Source" not in titles


# ---------------------------------------------------------------------------
# Import stubs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_preview_requires_file(client: AsyncClient, fresh_engine):
    """Import preview is now implemented — calling without a file returns 422."""
    token = await _admin_token(client, fresh_engine)
    resp = await client.post("/api/content/import/preview", headers=_auth(token))
    assert resp.status_code == 422  # missing required 'file' field


@pytest.mark.asyncio
async def test_import_commit_requires_file(client: AsyncClient, fresh_engine):
    """Import commit is now implemented — calling without a file returns 422."""
    token = await _admin_token(client, fresh_engine)
    resp = await client.post("/api/content/import/commit", headers=_auth(token))
    assert resp.status_code == 422  # missing required 'file' field
