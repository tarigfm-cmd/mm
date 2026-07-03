"""
Stabilization tests for the content governance backend.

These tests verify RBAC granularity, content lifecycle transitions,
version consistency, region rule enforcement, analytics data isolation,
and analytics aggregation correctness.
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import (
    ContentItem,
    ContentVersion,
    LearnerFailureAnalytics,
    RegionPublishingRule,
)
from app.models.identity import AuditLog, Organization, OrganizationMembership, Role, User
from app.core.security import hash_password

# ---------------------------------------------------------------------------
# Shared credentials
# ---------------------------------------------------------------------------

_ADMIN = {
    "email": "stabadmin@example.com",
    "username": "stabadmin",
    "password": "StabAdmin1!",
    "full_name": "Stab Admin",
}
_REVIEWER = {
    "email": "reviewer@example.com",
    "username": "reviewer01",
    "password": "Reviewer1!",
    "full_name": "Content Reviewer",
}
_LEARNER = {
    "email": "learner@example.com",
    "username": "learner01",
    "password": "Learner1!",
    "full_name": "Test Learner",
}
_INST_ADMIN = {
    "email": "instadmin@example.com",
    "username": "instadmin01",
    "password": "InstAdmin1!",
    "full_name": "Institution Admin",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _admin_token(client: AsyncClient, engine) -> str:
    """Register admin user, promote to superuser, return token."""
    await client.post("/api/auth/register", json=_ADMIN)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        result = await s.execute(select(User).where(User.email == _ADMIN["email"]))
        user = result.scalar_one()
        user.is_superuser = True
        await s.commit()
    return await _login(client, _ADMIN["email"], _ADMIN["password"])


async def _setup_role_user(
    engine,
    client: AsyncClient,
    creds: dict,
    role_name: str,
) -> tuple[str, uuid.UUID, uuid.UUID]:
    """
    Register user, create an org, add user to org with role_name.
    Returns (token, org_id, user_id).
    """
    await client.post("/api/auth/register", json=creds)

    async with AsyncSession(engine, expire_on_commit=False) as s:
        user_result = await s.execute(select(User).where(User.email == creds["email"]))
        user = user_result.scalar_one()

        slug = f"org-{role_name[:8]}-{creds['username'][:8]}"
        org = Organization(name=f"Org for {role_name}", slug=slug, org_type="university")
        s.add(org)
        await s.flush()

        role_result = await s.execute(select(Role).where(Role.name == role_name))
        role = role_result.scalar_one()

        s.add(OrganizationMembership(user_id=user.id, organization_id=org.id, role_id=role.id))
        await s.commit()

        org_id = org.id
        user_id = user.id

    token = await _login(client, creds["email"], creds["password"])
    return token, org_id, user_id


async def _create_item(client: AsyncClient, token: str) -> dict:
    resp = await client.post(
        "/api/content/items",
        json={"title": "Aspirin Case", "content_type": "case"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_version(client: AsyncClient, token: str, item_id: str) -> dict:
    resp = await client.post(
        f"/api/content/items/{item_id}/versions",
        json={"payload_json": {"q": "dose?"}, "change_summary": "v1"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_review(
    client: AsyncClient, token: str, item_id: str, decision: str = "approved",
    version_id: str | None = None,
) -> dict:
    body: dict = {"review_decision": decision}
    if version_id:
        body["content_version_id"] = version_id
    resp = await client.post(
        f"/api/content/items/{item_id}/reviews",
        json=body,
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _publish(client: AsyncClient, token: str, item_id: str, region: str = "UK") -> tuple[dict, int]:
    resp = await client.post(
        f"/api/content/items/{item_id}/publish",
        json={"region_code": region},
        headers=_auth(token),
    )
    return resp.json(), resp.status_code


# ---------------------------------------------------------------------------
# 1. RBAC granularity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_content_reviewer_can_submit_review(client: AsyncClient, fresh_engine):
    """A user with content.review permission can POST a clinical review."""
    admin_token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, admin_token)

    reviewer_token, _, _ = await _setup_role_user(fresh_engine, client, _REVIEWER, "content_reviewer")
    resp = await client.post(
        f"/api/content/items/{item['id']}/reviews",
        json={"review_decision": "approved"},
        headers=_auth(reviewer_token),
    )
    assert resp.status_code == 201
    assert resp.json()["review_decision"] == "approved"


@pytest.mark.asyncio
async def test_content_reviewer_cannot_publish(client: AsyncClient, fresh_engine):
    """A content_reviewer does not have content.publish — must receive 403."""
    admin_token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, admin_token)
    await _create_version(client, admin_token, item["id"])
    await _create_review(client, admin_token, item["id"])

    reviewer_token, _, _ = await _setup_role_user(fresh_engine, client, _REVIEWER, "content_reviewer")
    resp = await client.post(
        f"/api/content/items/{item['id']}/publish",
        json={"region_code": "UK"},
        headers=_auth(reviewer_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_institution_admin_can_publish(client: AsyncClient, fresh_engine):
    """institution_admin has content.publish and can publish items."""
    admin_token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, admin_token)
    await _create_version(client, admin_token, item["id"])
    await _create_review(client, admin_token, item["id"])

    ia_token, _, _ = await _setup_role_user(fresh_engine, client, _INST_ADMIN, "institution_admin")
    _, status_code = await _publish(client, ia_token, item["id"])
    assert status_code == 201


@pytest.mark.asyncio
async def test_learner_cannot_create_content_item(client: AsyncClient, fresh_engine):
    """A learner (no governance permissions) cannot create content items."""
    await client.post("/api/auth/register", json=_LEARNER)
    learner_token = await _login(client, _LEARNER["email"], _LEARNER["password"])
    resp = await client.post(
        "/api/content/items",
        json={"title": "Fake Case", "content_type": "case"},
        headers=_auth(learner_token),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 2. Content lifecycle status transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_new_version_on_draft_sets_pending_review(client: AsyncClient, fresh_engine):
    """Creating a version on a draft item advances status to pending_review."""
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    assert item["status"] == "draft"

    await _create_version(client, token, item["id"])
    resp = await client.get(f"/api/content/items/{item['id']}", headers=_auth(token))
    assert resp.json()["status"] == "pending_review"


@pytest.mark.asyncio
async def test_new_version_on_published_sets_needs_update(client: AsyncClient, fresh_engine):
    """Adding a version to a published item sets status to needs_update."""
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    await _create_version(client, token, item["id"])
    await _create_review(client, token, item["id"])
    await _publish(client, token, item["id"])

    # Item is now published; add another version
    await _create_version(client, token, item["id"])
    resp = await client.get(f"/api/content/items/{item['id']}", headers=_auth(token))
    assert resp.json()["status"] == "needs_update"


@pytest.mark.asyncio
async def test_rollback_on_published_item_sets_needs_update(client: AsyncClient, fresh_engine):
    """Rolling back a published item sets status to needs_update."""
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    v1 = await _create_version(client, token, item["id"])
    await _create_review(client, token, item["id"])
    await _publish(client, token, item["id"])

    # Add v2 so there's something to roll back from
    await _create_version(client, token, item["id"])
    # status is now needs_update; roll back to v1
    resp = await client.post(
        f"/api/content/items/{item['id']}/versions/rollback/{v1['id']}",
        headers=_auth(token),
    )
    assert resp.status_code == 201

    item_resp = await client.get(f"/api/content/items/{item['id']}", headers=_auth(token))
    assert item_resp.json()["status"] == "needs_update"


@pytest.mark.asyncio
async def test_rollback_on_pending_review_item_sets_pending_review(client: AsyncClient, fresh_engine):
    """Rolling back a pending_review item keeps status as pending_review."""
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    v1 = await _create_version(client, token, item["id"])  # status→pending_review
    await _create_version(client, token, item["id"])  # still pending_review

    resp = await client.post(
        f"/api/content/items/{item['id']}/versions/rollback/{v1['id']}",
        headers=_auth(token),
    )
    assert resp.status_code == 201
    item_resp = await client.get(f"/api/content/items/{item['id']}", headers=_auth(token))
    assert item_resp.json()["status"] == "pending_review"


@pytest.mark.asyncio
async def test_cannot_add_version_to_retired_item(client: AsyncClient, fresh_engine):
    """Creating a version on a retired item returns 409."""
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    # Force status to retired directly
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        row = await s.get(ContentItem, uuid.UUID(item["id"]))
        row.status = "retired"
        await s.commit()

    resp = await client.post(
        f"/api/content/items/{item['id']}/versions",
        json={"change_summary": "should fail"},
        headers=_auth(token),
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 3. Version consistency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_with_mismatched_version_id_rejected(client: AsyncClient, fresh_engine):
    """A review with content_version_id belonging to a different item returns 422."""
    token = await _admin_token(client, fresh_engine)
    item_a = await _create_item(client, token)
    item_b = await _create_item(client, token)
    v_b = await _create_version(client, token, item_b["id"])

    resp = await client.post(
        f"/api/content/items/{item_a['id']}/reviews",
        json={"review_decision": "approved", "content_version_id": v_b["id"]},
        headers=_auth(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_publish_blocked_when_review_is_for_old_version(client: AsyncClient, fresh_engine):
    """
    If the only approved review targets V1 (content_version_id=V1) and the
    current version is V2, publish must be rejected with 409.
    """
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    v1 = await _create_version(client, token, item["id"])
    # Review explicitly tied to v1
    await _create_review(client, token, item["id"], version_id=v1["id"])
    # Now add v2 — v1's review is now stale
    await _create_version(client, token, item["id"])

    _, status_code = await _publish(client, token, item["id"])
    assert status_code == 409


@pytest.mark.asyncio
async def test_publish_allowed_when_review_targets_current_version(client: AsyncClient, fresh_engine):
    """Review for the current version allows publish."""
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    await _create_version(client, token, item["id"])  # v1
    v2 = await _create_version(client, token, item["id"])  # v2 — current
    # Review for v2 explicitly
    await _create_review(client, token, item["id"], version_id=v2["id"])

    _, status_code = await _publish(client, token, item["id"])
    assert status_code == 201


@pytest.mark.asyncio
async def test_publish_allowed_when_review_has_no_version(client: AsyncClient, fresh_engine):
    """Review without content_version_id (NULL) applies to any current version."""
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    await _create_version(client, token, item["id"])
    # Review without specifying version (NULL)
    await _create_review(client, token, item["id"])

    _, status_code = await _publish(client, token, item["id"])
    assert status_code == 201


# ---------------------------------------------------------------------------
# 4. RegionPublishingRule enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_blocked_by_region_rule_status_constraint(client: AsyncClient, fresh_engine):
    """
    If an active RegionPublishingRule for 'AU' requires status 'clinically_approved'
    and the item is in 'pending_review', publish to 'AU' must fail with 409.
    """
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    await _create_version(client, token, item["id"])  # status → pending_review
    await _create_review(client, token, item["id"])

    # Insert a region rule that restricts AU publishing to clinically_approved
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        s.add(RegionPublishingRule(
            region_code="AU",
            allowed_statuses=["clinically_approved", "published"],
            is_active=True,
        ))
        await s.commit()

    # Item is in pending_review — rule blocks it
    _, status_code = await _publish(client, token, item["id"], region="AU")
    assert status_code == 409


@pytest.mark.asyncio
async def test_publish_allowed_when_region_rule_status_matches(client: AsyncClient, fresh_engine):
    """Publish proceeds when item status is in the rule's allowed_statuses."""
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    await _create_version(client, token, item["id"])
    await _create_review(client, token, item["id"])

    # Rule allows pending_review and clinically_approved for US
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        s.add(RegionPublishingRule(
            region_code="US",
            allowed_statuses=["pending_review", "clinically_approved"],
            is_active=True,
        ))
        await s.commit()

    # Item is in pending_review — rule allows it
    _, status_code = await _publish(client, token, item["id"], region="US")
    assert status_code == 201


@pytest.mark.asyncio
async def test_inactive_region_rule_is_not_enforced(client: AsyncClient, fresh_engine):
    """An inactive RegionPublishingRule does not block publish."""
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    await _create_version(client, token, item["id"])
    await _create_review(client, token, item["id"])

    # Inactive rule that would otherwise block
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        s.add(RegionPublishingRule(
            region_code="UK",
            allowed_statuses=["clinically_approved"],
            is_active=False,  # inactive
        ))
        await s.commit()

    _, status_code = await _publish(client, token, item["id"], region="UK")
    assert status_code == 201


# ---------------------------------------------------------------------------
# 5. Analytics data isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_org_weakness_map_blocked_for_non_member(client: AsyncClient, fresh_engine):
    """A user from org A cannot access the weakness map of org B."""
    await client.post("/api/auth/register", json=_INST_ADMIN)
    ia_token, org_a_id, _ = await _setup_role_user(
        fresh_engine, client, _INST_ADMIN, "institution_admin"
    )

    # Create org B that user is NOT a member of
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        org_b = Organization(name="Org B", slug="org-b-isolation", org_type="hospital")
        s.add(org_b)
        await s.commit()
        org_b_id = org_b.id

    resp = await client.get(
        f"/api/analytics/organization/{org_b_id}/weakness-map",
        headers=_auth(ia_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_org_weakness_map_allowed_for_own_org(client: AsyncClient, fresh_engine):
    """An institution_admin can access their own org's weakness map."""
    ia_token, org_id, _ = await _setup_role_user(
        fresh_engine, client, _INST_ADMIN, "institution_admin"
    )
    resp = await client.get(
        f"/api/analytics/organization/{org_id}/weakness-map",
        headers=_auth(ia_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["organization_id"] == str(org_id)
    assert "total_attempts" in data


# ---------------------------------------------------------------------------
# 6. Analytics aggregation correctness (SQLAlchemy cast fix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failure_hotspot_aggregation_with_real_data(client: AsyncClient, fresh_engine):
    """
    Verify that failure rate aggregation works with actual analytics records.
    This tests the SQLAlchemy cast(bool, Integer) fix — previously used
    func.cast() which generates invalid SQL for PostgreSQL.
    """
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    item_id = uuid.UUID(item["id"])

    # Insert 4 analytics records directly (2 red_flag failures, 1 counseling failure)
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        s.add(LearnerFailureAnalytics(content_item_id=item_id, score=0.2, failed_red_flag=True))
        s.add(LearnerFailureAnalytics(content_item_id=item_id, score=0.4, failed_red_flag=True, failed_counseling_point=True))
        s.add(LearnerFailureAnalytics(content_item_id=item_id, score=0.8, failed_red_flag=False))
        s.add(LearnerFailureAnalytics(content_item_id=item_id, score=0.9, failed_red_flag=False))
        await s.commit()

    resp = await client.get("/api/analytics/failure-hotspots", headers=_auth(token))
    assert resp.status_code == 200
    hotspots = resp.json()
    assert len(hotspots) >= 1
    target = next(h for h in hotspots if h["content_item_id"] == str(item_id))
    assert target["total_attempts"] == 4
    # 2 out of 4 = 0.5
    assert abs(target["red_flag_fail_rate"] - 0.5) < 0.001
    # 1 out of 4 = 0.25
    assert abs(target["counseling_fail_rate"] - 0.25) < 0.001


@pytest.mark.asyncio
async def test_content_failure_summary_with_real_data(client: AsyncClient, fresh_engine):
    """Content failure summary returns correct rates and total_attempts."""
    token = await _admin_token(client, fresh_engine)
    item = await _create_item(client, token)
    item_id = uuid.UUID(item["id"])

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        s.add(LearnerFailureAnalytics(content_item_id=item_id, score=0.3, failed_dose_calculation=True))
        s.add(LearnerFailureAnalytics(content_item_id=item_id, score=0.7, failed_dose_calculation=False))
        await s.commit()

    resp = await client.get(
        f"/api/analytics/content/{item['id']}/failure-summary",
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_attempts"] == 2
    assert abs(data["avg_score"] - 0.5) < 0.001
    assert abs(data["failure_breakdown"]["dose_calculation"] - 0.5) < 0.001


# ---------------------------------------------------------------------------
# 7. Audit log completeness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_governance_audit_events_are_written(client: AsyncClient, fresh_engine):
    """Every critical governance write emits an AuditLog row."""
    token = await _admin_token(client, fresh_engine)

    # item create
    item = await _create_item(client, token)

    # version create
    v1 = await _create_version(client, token, item["id"])

    # review create
    await _create_review(client, token, item["id"])

    # publish
    await _publish(client, token, item["id"])

    # unpublish
    await client.post(
        f"/api/content/items/{item['id']}/unpublish",
        json={"region_code": "UK"},
        headers=_auth(token),
    )

    # version rollback (create v2 first, then rollback to v1)
    await _create_version(client, token, item["id"])
    await client.post(
        f"/api/content/items/{item['id']}/versions/rollback/{v1['id']}",
        headers=_auth(token),
    )

    # approval batch
    await client.post(
        "/api/content/approval-batches",
        json={"batch_name": "Batch X", "approved_by_team_name": "Team", "approved_at": "2026-01-01T00:00:00Z"},
        headers=_auth(token),
    )

    # evidence source create
    ev_resp = await client.post(
        "/api/evidence/sources",
        json={"title": "NICE Guidance", "evidence_status": "active"},
        headers=_auth(token),
    )
    ev_id = ev_resp.json()["id"]

    # evidence source update
    await client.patch(
        f"/api/evidence/sources/{ev_id}",
        json={"evidence_status": "needs_review"},
        headers=_auth(token),
    )

    # Verify all 9 expected audit actions were logged
    expected_actions = {
        "content.item_created",
        "content.version_created",
        "content.review_created",
        "content.published",
        "content.unpublished",
        "content.version_rollback",
        "content.approval_batch_created",
        "content.evidence_source_created",
        "content.evidence_source_updated",
    }

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        result = await s.execute(
            select(AuditLog.action).where(AuditLog.action.in_(expected_actions))
        )
        logged_actions = {row[0] for row in result.all()}

    missing = expected_actions - logged_actions
    assert not missing, f"Missing audit events: {missing}"
