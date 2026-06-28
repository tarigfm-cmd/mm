"""
Tests for Interactive Training Engine Phase 2.

Covers:
- Training flow endpoint: correct steps per content type, hidden field safety
- Session start: creates session, requires published content, stores correct version
- Session submit: user ownership, idempotency, deterministic scoring, analytics creation
- Progress: completed_sessions, average_score_percent, user-scope isolation
- Security: hidden fields never appear before submission, reveal only after submit
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
    LearnerTrainingSession,
    PublicationRecord,
)
from app.models.identity import User

# ---------------------------------------------------------------------------
# Credentials — non-colliding with other test files
# ---------------------------------------------------------------------------

_ENG_A = {
    "email": "eng_a@example.com",
    "username": "eng_trn_a",
    "password": "EngA1!pass",
    "full_name": "Engine Learner A",
}
_ENG_B = {
    "email": "eng_b@example.com",
    "username": "eng_trn_b",
    "password": "EngB1!pass",
    "full_name": "Engine Learner B",
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


async def _make_published_item(
    engine,
    content_type: str = "case",
    region_code: str = "UK",
    payload: dict | None = None,
    make_published: bool = True,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Return (item_id, version_id)."""
    async with AsyncSession(engine, expire_on_commit=False) as s:
        item = ContentItem(
            title=f"Engine Test {content_type}",
            content_type=content_type,
            domain="Respiratory",
            difficulty="3",
            region_scope=[region_code],
            status="published" if make_published else "pending_review",
            external_id=f"ENG-{uuid.uuid4().hex[:8]}",
        )
        s.add(item)
        await s.flush()

        version = ContentVersion(
            content_item_id=item.id,
            version_number=1,
            payload_json=payload or {"patient_profile": "Alice, 30F", "presenting_complaint": "Cough"},
            is_current=True,
        )
        s.add(version)
        await s.flush()
        item.current_version_id = version.id

        if make_published:
            pub = PublicationRecord(
                content_item_id=item.id,
                content_version_id=version.id,
                region_code=region_code,
                publication_status="published",
                published_at=datetime.now(timezone.utc),
            )
            s.add(pub)

        await s.commit()
        return item.id, version.id


# ---------------------------------------------------------------------------
# 1. Training flow — steps for case
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_training_flow_returns_steps_for_case(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    item_id, _ = await _make_published_item(fresh_engine, content_type="case")
    r = await client.get(
        f"/api/learn/content/{item_id}/training-flow",
        params={"region_code": "UK"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["content_type"] == "case"
    assert data["total_steps"] == 4
    step_types = [s["step_type"] for s in data["steps"]]
    assert "briefing" in step_types
    assert "decision" in step_types
    assert "counseling" in step_types


# ---------------------------------------------------------------------------
# 2. Training flow — steps for drill
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_training_flow_returns_steps_for_drill(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    payload = {"prompt": "What is the max daily dose of paracetamol?", "correct_answer_or_expected_response": "4g"}
    item_id, _ = await _make_published_item(fresh_engine, content_type="drill", payload=payload)
    r = await client.get(
        f"/api/learn/content/{item_id}/training-flow",
        params={"region_code": "UK"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["content_type"] == "drill"
    assert data["total_steps"] == 2


# ---------------------------------------------------------------------------
# 3. Training flow — steps for prescription_screening
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_training_flow_returns_steps_for_prescription_screening(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    item_id, _ = await _make_published_item(fresh_engine, content_type="prescription_screening")
    r = await client.get(
        f"/api/learn/content/{item_id}/training-flow",
        params={"region_code": "UK"},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_steps"] == 4


# ---------------------------------------------------------------------------
# 4. Training flow — hides answer keys before submission
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_training_flow_hides_answer_keys(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    payload = {
        "patient_profile": "Bob, 45M",
        "presenting_complaint": "Chest pain",
        "expected_decision": "Refer urgently",
        "hidden_risk": "Possible MI",
        "failure_mode": "Missing red flag",
        "critical_fail": True,
        "scoring_rubric": "1 point for referral",
    }
    item_id, _ = await _make_published_item(fresh_engine, content_type="case", payload=payload)
    r = await client.get(
        f"/api/learn/content/{item_id}/training-flow",
        params={"region_code": "UK"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    raw = r.text
    for hidden in ("expected_decision", "hidden_risk", "failure_mode", "critical_fail", "scoring_rubric"):
        assert hidden not in raw, f"Hidden field '{hidden}' leaked in training-flow response"


# ---------------------------------------------------------------------------
# 5. Training flow — blocks unpublished content (404)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_training_flow_blocks_unpublished_content(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    item_id, _ = await _make_published_item(fresh_engine, content_type="case", make_published=False)
    r = await client.get(
        f"/api/learn/content/{item_id}/training-flow",
        params={"region_code": "UK"},
        headers=_auth(token),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 6. Training flow — wrong region returns 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_training_flow_wrong_region_404(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    item_id, _ = await _make_published_item(fresh_engine, content_type="case", region_code="UK")
    r = await client.get(
        f"/api/learn/content/{item_id}/training-flow",
        params={"region_code": "AU"},
        headers=_auth(token),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 7. Session start — requires published content
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_start_requires_published_content(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    item_id, _ = await _make_published_item(fresh_engine, make_published=False)
    r = await client.post(
        f"/api/learn/content/{item_id}/sessions",
        json={"region_code": "UK"},
        headers=_auth(token),
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 8. Session start — stores current published version
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_start_stores_published_version(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    item_id, version_id = await _make_published_item(fresh_engine)
    r = await client.post(
        f"/api/learn/content/{item_id}/sessions",
        json={"region_code": "UK"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["content_item_id"] == str(item_id)
    assert data["content_version_id"] == str(version_id)
    assert data["status"] == "started"


# ---------------------------------------------------------------------------
# 9. Session start — creates total_steps matching flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_start_total_steps_matches_flow(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    item_id, _ = await _make_published_item(fresh_engine, content_type="case")
    r = await client.post(
        f"/api/learn/content/{item_id}/sessions",
        json={"region_code": "UK"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["total_steps"] == 4


# ---------------------------------------------------------------------------
# 10. User cannot submit another user's session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_cannot_submit_another_users_session(client, fresh_engine):
    token_a = await _register_and_login(client, _ENG_A)
    token_b = await _register_and_login(client, _ENG_B)
    item_id, _ = await _make_published_item(fresh_engine)

    # A starts a session
    r = await client.post(
        f"/api/learn/content/{item_id}/sessions",
        json={"region_code": "UK"},
        headers=_auth(token_a),
    )
    session_id = r.json()["session_id"]

    # B tries to submit it
    r = await client.post(
        f"/api/learn/sessions/{session_id}/submit",
        json={"action_selected": "Refer to GP"},
        headers=_auth(token_b),
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 11. User cannot submit completed session twice
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cannot_submit_completed_session_twice(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    item_id, _ = await _make_published_item(fresh_engine)

    r = await client.post(
        f"/api/learn/content/{item_id}/sessions",
        json={"region_code": "UK"},
        headers=_auth(token),
    )
    session_id = r.json()["session_id"]

    submit = {"action_selected": "Refer to GP"}
    r1 = await client.post(f"/api/learn/sessions/{session_id}/submit", json=submit, headers=_auth(token))
    assert r1.status_code == 200

    r2 = await client.post(f"/api/learn/sessions/{session_id}/submit", json=submit, headers=_auth(token))
    assert r2.status_code == 409


# ---------------------------------------------------------------------------
# 12. Submit calculates deterministic score for a case
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_deterministic_score_correct_case(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    payload = {"patient_profile": "Alice", "expected_decision": "Refer to GP"}
    item_id, _ = await _make_published_item(fresh_engine, content_type="case", payload=payload)

    r = await client.post(
        f"/api/learn/content/{item_id}/sessions",
        json={"region_code": "UK"},
        headers=_auth(token),
    )
    session_id = r.json()["session_id"]

    r = await client.post(
        f"/api/learn/sessions/{session_id}/submit",
        json={"action_selected": "refer to gp"},  # case-insensitive
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["score"] == 1.0
    assert data["score_percent"] == 100.0
    assert "triage_or_referral_decision" not in data["failed_dimensions"]


# ---------------------------------------------------------------------------
# 13. Submit calculates deterministic score — wrong answer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_deterministic_score_wrong_case(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    payload = {"patient_profile": "Alice", "expected_decision": "Refer to GP"}
    item_id, _ = await _make_published_item(fresh_engine, content_type="case", payload=payload)

    r = await client.post(f"/api/learn/content/{item_id}/sessions", json={"region_code": "UK"}, headers=_auth(token))
    session_id = r.json()["session_id"]

    r = await client.post(
        f"/api/learn/sessions/{session_id}/submit",
        json={"action_selected": "Advise only"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["score"] == 0.0
    assert "triage_or_referral_decision" in data["failed_dimensions"]


# ---------------------------------------------------------------------------
# 14. Submit marks not_assessable dimensions cleanly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_marks_not_assessable_dimensions(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    # osce_station has no structured expected answer — all not_assessable
    item_id, _ = await _make_published_item(
        fresh_engine, content_type="osce_station",
        payload={"candidate_task": "Counsel patient on asthma inhaler technique"}
    )
    r = await client.post(f"/api/learn/content/{item_id}/sessions", json={"region_code": "UK"}, headers=_auth(token))
    session_id = r.json()["session_id"]

    r = await client.post(
        f"/api/learn/sessions/{session_id}/submit",
        json={},
        headers=_auth(token),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["score"] is None
    assert len(data["not_assessable_dimensions"]) > 0
    assert len(data["failed_dimensions"]) == 0


# ---------------------------------------------------------------------------
# 15. Submit creates LearnerFailureAnalytics record
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_creates_learner_failure_analytics(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    item_id, _ = await _make_published_item(fresh_engine)
    r = await client.post(f"/api/learn/content/{item_id}/sessions", json={"region_code": "UK"}, headers=_auth(token))
    session_id = r.json()["session_id"]

    await client.post(f"/api/learn/sessions/{session_id}/submit", json={}, headers=_auth(token))

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        count = (await s.execute(
            select(LearnerFailureAnalytics)
            .where(LearnerFailureAnalytics.content_item_id == item_id)
        )).scalars().all()
    assert len(count) == 1


# ---------------------------------------------------------------------------
# 16. Hidden fields never appear in pre-submit responses
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hidden_fields_never_in_pre_submit_responses(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    payload = {
        "patient_profile": "Eve",
        "expected_decision": "Refer urgently",
        "hidden_risk": "Anaphylaxis",
        "failure_mode": "Missed allergy",
        "scoring_rubric": "1pt for urgency",
    }
    item_id, _ = await _make_published_item(fresh_engine, content_type="case", payload=payload)

    # Session start must not leak
    r_start = await client.post(
        f"/api/learn/content/{item_id}/sessions",
        json={"region_code": "UK"},
        headers=_auth(token),
    )
    assert r_start.status_code == 201
    raw_start = r_start.text
    for hidden in ("expected_decision", "hidden_risk", "failure_mode", "scoring_rubric"):
        assert hidden not in raw_start

    # Detail endpoint must not leak
    r_detail = await client.get(
        f"/api/learn/content/{item_id}",
        params={"region_code": "UK"},
        headers=_auth(token),
    )
    raw_detail = r_detail.text
    for hidden in ("expected_decision", "hidden_risk", "failure_mode", "scoring_rubric"):
        assert hidden not in raw_detail, f"Hidden field '{hidden}' leaked in detail"


# ---------------------------------------------------------------------------
# 17. Reveal fields appear in submit response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reveal_fields_appear_after_submission(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    payload = {
        "patient_profile": "Frank",
        "expected_decision": "Refer to GP",
        "hidden_risk": "Uncontrolled hypertension",
    }
    item_id, _ = await _make_published_item(fresh_engine, content_type="case", payload=payload)
    r = await client.post(f"/api/learn/content/{item_id}/sessions", json={"region_code": "UK"}, headers=_auth(token))
    session_id = r.json()["session_id"]

    r = await client.post(
        f"/api/learn/sessions/{session_id}/submit",
        json={"action_selected": "Refer to GP"},
        headers=_auth(token),
    )
    data = r.json()
    reveal = data["reveal_summary"]
    assert "Expected decision" in reveal or "Hidden risk" in reveal, \
        f"Expected reveal_summary to contain revealed fields. Got: {reveal}"


# ---------------------------------------------------------------------------
# 18. Progress includes completed_sessions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_progress_includes_completed_sessions(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    item_id, _ = await _make_published_item(fresh_engine)

    r = await client.post(f"/api/learn/content/{item_id}/sessions", json={"region_code": "UK"}, headers=_auth(token))
    session_id = r.json()["session_id"]
    await client.post(f"/api/learn/sessions/{session_id}/submit", json={}, headers=_auth(token))

    r = await client.get("/api/learn/progress", headers=_auth(token))
    assert r.status_code == 200
    data = r.json()
    assert data["completed_sessions"] == 1


# ---------------------------------------------------------------------------
# 19. Progress includes average_score_percent from sessions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_progress_includes_average_score_percent(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    payload = {"patient_profile": "Grace", "expected_decision": "Refer to GP"}
    item_id, _ = await _make_published_item(fresh_engine, content_type="case", payload=payload)

    r = await client.post(f"/api/learn/content/{item_id}/sessions", json={"region_code": "UK"}, headers=_auth(token))
    session_id = r.json()["session_id"]
    await client.post(
        f"/api/learn/sessions/{session_id}/submit",
        json={"action_selected": "refer to gp"},
        headers=_auth(token),
    )

    r = await client.get("/api/learn/progress", headers=_auth(token))
    data = r.json()
    assert data["average_score_percent"] == 100.0


# ---------------------------------------------------------------------------
# 20. Progress is scoped to current user only
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_progress_is_user_scoped(client, fresh_engine):
    token_a = await _register_and_login(client, _ENG_A)
    token_b = await _register_and_login(client, _ENG_B)
    item_id, _ = await _make_published_item(fresh_engine)

    # A creates and submits a session
    r = await client.post(f"/api/learn/content/{item_id}/sessions", json={"region_code": "UK"}, headers=_auth(token_a))
    sess_id = r.json()["session_id"]
    await client.post(f"/api/learn/sessions/{sess_id}/submit", json={}, headers=_auth(token_a))

    # B's progress should show 0 completed sessions
    r = await client.get("/api/learn/progress", headers=_auth(token_b))
    data = r.json()
    assert data["completed_sessions"] == 0
    assert data["total_attempts"] == 0


# ---------------------------------------------------------------------------
# 21. Drill: correct answer scores 100%
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_drill_correct_answer_scores_100(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    payload = {"prompt": "Maximum daily dose of ibuprofen?", "correct_answer_or_expected_response": "2400mg"}
    item_id, _ = await _make_published_item(fresh_engine, content_type="drill", payload=payload)

    r = await client.post(f"/api/learn/content/{item_id}/sessions", json={"region_code": "UK"}, headers=_auth(token))
    sess_id = r.json()["session_id"]
    r = await client.post(
        f"/api/learn/sessions/{sess_id}/submit",
        json={"answer_text": "2400MG"},  # case insensitive
        headers=_auth(token),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["score"] == 1.0
    assert data["score_percent"] == 100.0


# ---------------------------------------------------------------------------
# 22. Prescription screening: correct action scores 100%
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prescription_screening_correct_action(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    payload = {"patient_profile": "Harry", "expected_pharmacist_action": "Query with prescriber"}
    item_id, _ = await _make_published_item(fresh_engine, content_type="prescription_screening", payload=payload)

    r = await client.post(f"/api/learn/content/{item_id}/sessions", json={"region_code": "UK"}, headers=_auth(token))
    sess_id = r.json()["session_id"]
    r = await client.post(
        f"/api/learn/sessions/{sess_id}/submit",
        json={"action_selected": "query with prescriber"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["score"] == 1.0


# ---------------------------------------------------------------------------
# 23. Session submit requires authentication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_submit_requires_authentication(client, fresh_engine):
    r = await client.post("/api/learn/sessions/00000000-0000-0000-0000-000000000000/submit", json={})
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 24. Recent sessions appear in progress
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recent_sessions_in_progress(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    item_id, _ = await _make_published_item(fresh_engine)

    r = await client.post(f"/api/learn/content/{item_id}/sessions", json={"region_code": "UK"}, headers=_auth(token))
    sess_id = r.json()["session_id"]
    await client.post(f"/api/learn/sessions/{sess_id}/submit", json={}, headers=_auth(token))

    r = await client.get("/api/learn/progress", headers=_auth(token))
    data = r.json()
    assert len(data["recent_sessions"]) >= 1
    assert data["recent_sessions"][0]["status"] == "completed"


# ---------------------------------------------------------------------------
# 25. Dimension feedback list is returned on submit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dimension_feedback_returned_on_submit(client, fresh_engine):
    token = await _register_and_login(client, _ENG_A)
    item_id, _ = await _make_published_item(fresh_engine, content_type="case")
    r = await client.post(f"/api/learn/content/{item_id}/sessions", json={"region_code": "UK"}, headers=_auth(token))
    sess_id = r.json()["session_id"]
    r = await client.post(f"/api/learn/sessions/{sess_id}/submit", json={}, headers=_auth(token))
    data = r.json()
    assert "dimension_feedback" in data
    assert len(data["dimension_feedback"]) > 0
    for item in data["dimension_feedback"]:
        assert item["status"] in ("passed", "failed", "not_assessable")
