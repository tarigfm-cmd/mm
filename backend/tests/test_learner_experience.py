"""
Tests for Learner-Facing Published Content Experience milestone.

Covers:
- Browse endpoint returns only published content
- Region filter works correctly
- content_type / difficulty / search filters
- Detail endpoint: 404 for unpublished/wrong-region; safe_payload strips answer keys
- Attempt endpoint: 404 for unpublished; creates analytics record; returns score/feedback
- Progress endpoint: user-scoped; excludes other users' data
"""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.governance import (
    ContentItem,
    ContentVersion,
    LearnerFailureAnalytics,
    PublicationRecord,
)
from app.models.identity import User

# ---------------------------------------------------------------------------
# Shared credentials — non-colliding with other test files
# ---------------------------------------------------------------------------

_LEARNER_A = {
    "email": "lrn_a@example.com",
    "username": "lrna",
    "password": "LearnerA1!",
    "full_name": "Learner A",
}
_LEARNER_B = {
    "email": "lrn_b@example.com",
    "username": "lrnb",
    "password": "LearnerB1!",
    "full_name": "Learner B",
}
_ADMIN = {
    "email": "lrn_admin@example.com",
    "username": "lrnadmin",
    "password": "LrnAdmin1!",
    "full_name": "Learner Test Admin",
}


async def _login(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register_and_login(client: AsyncClient, creds: dict) -> str:
    await client.post("/api/auth/register", json=creds)
    return await _login(client, creds["email"], creds["password"])


async def _make_admin(engine, email: str) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as s:
        user = (await s.execute(select(User).where(User.email == email))).scalar_one()
        user.is_superuser = True
        await s.commit()


async def _create_published_item(
    engine,
    title: str = "Test Case",
    content_type: str = "case",
    region_code: str = "UK",
    domain: str = "Respiratory",
    difficulty: str = "3",
    external_id: str | None = None,
    payload: dict | None = None,
    make_published: bool = True,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create a ContentItem + ContentVersion + PublicationRecord in the DB.
    Returns (item_id, version_id, publication_id).
    """
    async with AsyncSession(engine, expire_on_commit=False) as s:
        item = ContentItem(
            title=title,
            content_type=content_type,
            domain=domain,
            difficulty=difficulty,
            region_scope=[region_code],
            status="published" if make_published else "pending_review",
            external_id=external_id or f"EXT-{uuid.uuid4().hex[:8]}",
        )
        s.add(item)
        await s.flush()

        version = ContentVersion(
            content_item_id=item.id,
            version_number=1,
            payload_json=payload or {"prompt": "What is the clinical presentation?"},
            is_current=True,
        )
        s.add(version)
        await s.flush()

        item.current_version_id = version.id

        pub = None
        if make_published:
            pub = PublicationRecord(
                content_item_id=item.id,
                content_version_id=version.id,
                region_code=region_code,
                publication_status="published",
                published_at=datetime.now(timezone.utc),
            )
            s.add(pub)
            await s.flush()

        await s.commit()

        pub_id = pub.id if pub else uuid.uuid4()
        return item.id, version.id, pub_id


# ===========================================================================
# Browse endpoint tests
# ===========================================================================


@pytest.mark.asyncio
async def test_browse_returns_only_published(client: AsyncClient, fresh_engine):
    """Published items appear; pending_review items do not."""
    token = await _register_and_login(client, _LEARNER_A)

    published_id, _, _ = await _create_published_item(fresh_engine, title="Published Case")
    await _create_published_item(
        fresh_engine, title="Pending Case", make_published=False
    )

    r = await client.get("/api/learn/content", params={"region_code": "UK"}, headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    ids = [i["id"] for i in data["items"]]
    assert str(published_id) in ids
    # The pending item must not appear
    titles = [i["title"] for i in data["items"]]
    assert "Pending Case" not in titles


@pytest.mark.asyncio
async def test_browse_region_filter(client: AsyncClient, fresh_engine):
    """UK published items do not appear when browsing US."""
    token = await _register_and_login(client, _LEARNER_A)

    await _create_published_item(fresh_engine, title="UK Only", region_code="UK")

    r = await client.get("/api/learn/content", params={"region_code": "US"}, headers=_auth(token))
    assert r.status_code == 200
    titles = [i["title"] for i in r.json()["items"]]
    assert "UK Only" not in titles


@pytest.mark.asyncio
async def test_browse_content_type_filter(client: AsyncClient, fresh_engine):
    token = await _register_and_login(client, _LEARNER_A)

    await _create_published_item(fresh_engine, title="A Case", content_type="case")
    await _create_published_item(fresh_engine, title="A Drill", content_type="drill")

    r = await client.get(
        "/api/learn/content",
        params={"region_code": "UK", "content_type": "drill"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i["content_type"] == "drill" for i in items)
    assert any(i["title"] == "A Drill" for i in items)
    assert not any(i["title"] == "A Case" for i in items)


@pytest.mark.asyncio
async def test_browse_difficulty_filter(client: AsyncClient, fresh_engine):
    token = await _register_and_login(client, _LEARNER_A)

    await _create_published_item(fresh_engine, title="Easy", difficulty="1")
    await _create_published_item(fresh_engine, title="Hard", difficulty="5")

    r = await client.get(
        "/api/learn/content",
        params={"region_code": "UK", "difficulty": "1"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i["difficulty"] == "1" for i in items)


@pytest.mark.asyncio
async def test_browse_search_filter(client: AsyncClient, fresh_engine):
    token = await _register_and_login(client, _LEARNER_A)

    await _create_published_item(
        fresh_engine, title="Metformin Case", external_id="BNF-MET-001"
    )
    await _create_published_item(fresh_engine, title="Aspirin Case")

    r = await client.get(
        "/api/learn/content",
        params={"region_code": "UK", "search": "Metformin"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Metformin Case"


@pytest.mark.asyncio
async def test_browse_search_by_external_id(client: AsyncClient, fresh_engine):
    token = await _register_and_login(client, _LEARNER_A)

    await _create_published_item(fresh_engine, title="Insulin Case", external_id="BNF-INS-999")

    r = await client.get(
        "/api/learn/content",
        params={"region_code": "UK", "search": "BNF-INS-999"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["external_id"] == "BNF-INS-999" for i in items)


@pytest.mark.asyncio
async def test_browse_includes_version_id(client: AsyncClient, fresh_engine):
    token = await _register_and_login(client, _LEARNER_A)

    _, version_id, _ = await _create_published_item(fresh_engine, title="Version Check")

    r = await client.get("/api/learn/content", params={"region_code": "UK"}, headers=_auth(token))
    assert r.status_code == 200
    matching = [i for i in r.json()["items"] if i["title"] == "Version Check"]
    assert matching
    assert matching[0]["version_id"] == str(version_id)
    assert matching[0]["version_number"] == 1


@pytest.mark.asyncio
async def test_browse_invalid_region_422(client: AsyncClient, fresh_engine):
    token = await _register_and_login(client, _LEARNER_A)
    r = await client.get(
        "/api/learn/content", params={"region_code": "INVALID"}, headers=_auth(token)
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_browse_unauthenticated_requires_auth(client: AsyncClient, fresh_engine):
    r = await client.get("/api/learn/content", params={"region_code": "UK"})
    assert r.status_code in (401, 403)  # HTTPBearer returns 403 when no token provided


# ===========================================================================
# Detail endpoint tests
# ===========================================================================


@pytest.mark.asyncio
async def test_detail_returns_published_item(client: AsyncClient, fresh_engine):
    token = await _register_and_login(client, _LEARNER_A)

    item_id, _, _ = await _create_published_item(
        fresh_engine,
        title="Detail Test",
        payload={"prompt": "Patient presents with cough", "context": "OTC"},
    )

    r = await client.get(
        f"/api/learn/content/{item_id}",
        params={"region_code": "UK"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == str(item_id)
    assert data["title"] == "Detail Test"
    assert "version_id" in data
    assert "safe_payload" in data


@pytest.mark.asyncio
async def test_detail_404_for_unpublished(client: AsyncClient, fresh_engine):
    token = await _register_and_login(client, _LEARNER_A)

    item_id, _, _ = await _create_published_item(fresh_engine, make_published=False)

    r = await client.get(
        f"/api/learn/content/{item_id}",
        params={"region_code": "UK"},
        headers=_auth(token),
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_detail_404_wrong_region(client: AsyncClient, fresh_engine):
    token = await _register_and_login(client, _LEARNER_A)

    item_id, _, _ = await _create_published_item(fresh_engine, region_code="UK")

    r = await client.get(
        f"/api/learn/content/{item_id}",
        params={"region_code": "US"},
        headers=_auth(token),
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_detail_safe_payload_strips_answer_keys(client: AsyncClient, fresh_engine):
    """Answer keys must not appear in the detail payload before submission."""
    token = await _register_and_login(client, _LEARNER_A)

    evil_payload = {
        "prompt": "Visible question text",
        "correct_answer_or_expected_response": "SECRET ANSWER",
        "expected_decision": "SECRET DECISION",
        "expected_pharmacist_action": "SECRET ACTION",
        "hidden_risk": "HIDDEN RISK",
        "failure_mode": "FAILURE MODE",
        "critical_fail": "CRITICAL FAIL",
        "scoring_rubric": "RUBRIC",
    }
    item_id, _, _ = await _create_published_item(fresh_engine, payload=evil_payload)

    r = await client.get(
        f"/api/learn/content/{item_id}",
        params={"region_code": "UK"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    safe = r.json()["safe_payload"]
    assert safe is not None
    assert "correct_answer_or_expected_response" not in safe
    assert "expected_decision" not in safe
    assert "expected_pharmacist_action" not in safe
    assert "hidden_risk" not in safe
    assert "failure_mode" not in safe
    assert "critical_fail" not in safe
    assert "scoring_rubric" not in safe
    assert safe.get("prompt") == "Visible question text"


@pytest.mark.asyncio
async def test_detail_no_admin_metadata(client: AsyncClient, fresh_engine):
    """Learner detail must not expose admin/review internals."""
    token = await _register_and_login(client, _LEARNER_A)

    item_id, _, _ = await _create_published_item(fresh_engine)

    r = await client.get(
        f"/api/learn/content/{item_id}",
        params={"region_code": "UK"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    data = r.json()
    assert "created_by" not in data
    assert "content_hash" not in data
    assert "source_file_name" not in data
    assert "reviewer_user_id" not in data
    assert "approval_batch_id" not in data


# ===========================================================================
# Attempt endpoint tests
# ===========================================================================


@pytest.mark.asyncio
async def test_attempt_404_for_unpublished(client: AsyncClient, fresh_engine):
    token = await _register_and_login(client, _LEARNER_A)

    item_id, _, _ = await _create_published_item(fresh_engine, make_published=False)

    r = await client.post(
        f"/api/learn/content/{item_id}/attempt",
        json={"region_code": "UK"},
        headers=_auth(token),
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_attempt_creates_analytics_record(client: AsyncClient, fresh_engine):
    token = await _register_and_login(client, _LEARNER_A)

    item_id, _, _ = await _create_published_item(fresh_engine)

    r = await client.post(
        f"/api/learn/content/{item_id}/attempt",
        json={"region_code": "UK", "learner_response": "Some answer"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    data = r.json()
    assert "attempt_id" in data
    assert "feedback" in data
    assert "failed_dimensions" in data
    assert "recommended_next_step" in data

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        record = await s.get(LearnerFailureAnalytics, uuid.UUID(data["attempt_id"]))
        assert record is not None
        assert record.content_item_id == item_id


@pytest.mark.asyncio
async def test_attempt_drill_scoring_correct(client: AsyncClient, fresh_engine):
    """Drill with exact answer match returns score=1.0."""
    token = await _register_and_login(client, _LEARNER_A)

    item_id, _, _ = await _create_published_item(
        fresh_engine,
        content_type="drill",
        payload={
            "prompt": "What is the max dose of paracetamol per day?",
            "correct_answer_or_expected_response": "4g",
        },
    )

    r = await client.post(
        f"/api/learn/content/{item_id}/attempt",
        json={"region_code": "UK", "learner_response": "4g"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    data = r.json()
    assert data["score"] == 1.0


@pytest.mark.asyncio
async def test_attempt_drill_scoring_incorrect(client: AsyncClient, fresh_engine):
    """Drill with wrong answer returns score=0.0."""
    token = await _register_and_login(client, _LEARNER_A)

    item_id, _, _ = await _create_published_item(
        fresh_engine,
        content_type="drill",
        payload={
            "prompt": "What is the max dose of paracetamol per day?",
            "correct_answer_or_expected_response": "4g",
        },
    )

    r = await client.post(
        f"/api/learn/content/{item_id}/attempt",
        json={"region_code": "UK", "learner_response": "2g"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    data = r.json()
    assert data["score"] == 0.0


@pytest.mark.asyncio
async def test_attempt_no_structured_score_returns_none(client: AsyncClient, fresh_engine):
    """Items without structured scoring return score=None."""
    token = await _register_and_login(client, _LEARNER_A)

    item_id, _, _ = await _create_published_item(
        fresh_engine,
        content_type="case",
        payload={"prompt": "Describe the clinical approach"},
    )

    r = await client.post(
        f"/api/learn/content/{item_id}/attempt",
        json={"region_code": "UK"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["score"] is None


@pytest.mark.asyncio
async def test_attempt_records_failure_dimensions(client: AsyncClient, fresh_engine):
    """Explicit False flags create corresponding failed_* dimensions."""
    token = await _register_and_login(client, _LEARNER_A)

    item_id, _, _ = await _create_published_item(fresh_engine, content_type="case")

    r = await client.post(
        f"/api/learn/content/{item_id}/attempt",
        json={
            "region_code": "UK",
            "red_flag_identified": False,
            "counseling_point_selected": False,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    dims = r.json()["failed_dimensions"]
    assert "red_flag" in dims
    assert "counseling_point" in dims


@pytest.mark.asyncio
async def test_attempt_invalid_region_422(client: AsyncClient, fresh_engine):
    token = await _register_and_login(client, _LEARNER_A)
    item_id, _, _ = await _create_published_item(fresh_engine)

    r = await client.post(
        f"/api/learn/content/{item_id}/attempt",
        json={"region_code": "INVALID"},
        headers=_auth(token),
    )
    assert r.status_code == 422


# ===========================================================================
# Progress endpoint tests
# ===========================================================================


@pytest.mark.asyncio
async def test_progress_empty_for_new_user(client: AsyncClient, fresh_engine):
    token = await _register_and_login(client, _LEARNER_A)

    r = await client.get("/api/learn/progress", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["total_attempts"] == 0
    assert data["average_score"] is None
    assert data["recent_attempts"] == []


@pytest.mark.asyncio
async def test_progress_reflects_attempts(client: AsyncClient, fresh_engine):
    token = await _register_and_login(client, _LEARNER_A)

    item_id, _, _ = await _create_published_item(
        fresh_engine,
        content_type="drill",
        payload={"correct_answer_or_expected_response": "aspirin"},
    )

    await client.post(
        f"/api/learn/content/{item_id}/attempt",
        json={"region_code": "UK", "learner_response": "aspirin"},
        headers=_auth(token),
    )

    r = await client.get("/api/learn/progress", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["total_attempts"] == 1
    assert data["average_score"] == 1.0
    assert len(data["recent_attempts"]) == 1
    assert data["attempts_by_content_type"].get("drill", 0) == 1


@pytest.mark.asyncio
async def test_progress_is_user_scoped(client: AsyncClient, fresh_engine):
    """Learner A's progress must not include Learner B's attempts."""
    token_a = await _register_and_login(client, _LEARNER_A)
    token_b = await _register_and_login(client, _LEARNER_B)

    item_id, _, _ = await _create_published_item(fresh_engine, content_type="drill",
        payload={"correct_answer_or_expected_response": "ans"})

    # Learner B submits an attempt
    await client.post(
        f"/api/learn/content/{item_id}/attempt",
        json={"region_code": "UK", "learner_response": "ans"},
        headers=_auth(token_b),
    )

    # Learner A's progress should still be empty
    r_a = await client.get("/api/learn/progress", headers=_auth(token_a))
    assert r_a.json()["total_attempts"] == 0


@pytest.mark.asyncio
async def test_progress_weakness_breakdown(client: AsyncClient, fresh_engine):
    token = await _register_and_login(client, _LEARNER_A)

    item_id, _, _ = await _create_published_item(fresh_engine)

    await client.post(
        f"/api/learn/content/{item_id}/attempt",
        json={"region_code": "UK", "red_flag_identified": False},
        headers=_auth(token),
    )

    r = await client.get("/api/learn/progress", headers=_auth(token))
    wb = r.json()["weakness_breakdown"]
    # Phase 2: dimension keys use full scoring engine names
    assert "red_flag_recognition" in wb
    assert wb["red_flag_recognition"] == 1.0
