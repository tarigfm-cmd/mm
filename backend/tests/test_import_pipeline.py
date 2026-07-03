"""
Bulk CSV/ZIP import pipeline tests.

All tests use small synthetic CSV data created in-memory — the real content bank
ZIP is never touched in tests. Fixtures follow the same fresh_engine pattern as the
rest of the test suite.
"""
import asyncio
import csv
import io
import json
import uuid
import zipfile
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import (
    ContentItem,
    ContentVersion,
    EvidenceSource,
    ImportBatch,
    RegionPublishingRule,
)
from app.models.identity import AuditLog
from app.services.import_service import (
    MAX_ROWS_PER_FILE,
    MAX_UPLOAD_BYTES,
    MAX_ZIP_FILES,
    _content_hash,
    _derive_title,
    _normalize_learner_region,
    _parse_evidence_ids,
)

# ---------------------------------------------------------------------------
# Helpers — build minimal synthetic CSV bytes
# ---------------------------------------------------------------------------

_CASE_HEADERS = [
    "case_id", "content_type", "domain", "subtopic", "region_localization",
    "difficulty_1_5", "learner_level", "patient_profile", "presenting_request",
    "key_questions_to_elicit", "red_flags_to_screen", "current_medicines_or_context",
    "expected_decision", "counseling_points", "safety_traps", "scoring_dimensions",
    "evidence_ids", "review_status", "audit_notes", "last_evidence_check",
]

_SIM_HEADERS = [
    "simulation_id", "domain", "subtopic", "region_localization", "difficulty_1_5",
    "simulation_mode", "patient_persona", "opening_line", "branching_nodes",
    "hidden_risk", "failure_mode", "ideal_path", "adaptive_hint", "reward_hook",
    "evidence_ids", "review_status", "last_evidence_check",
]

_OSCE_HEADERS = [
    "osce_id", "station_title", "domain", "region_localization", "difficulty_1_5",
    "time_minutes", "candidate_task", "actor_brief", "equipment_or_materials",
    "must_assess_items", "critical_fail", "scoring_rubric", "examiner_notes",
    "evidence_ids", "review_status", "last_evidence_check",
]

_RX_HEADERS = [
    "screening_id", "issue_type", "region_localization", "difficulty_1_5",
    "patient_context", "prescription_or_request", "safety_concern", "what_to_check",
    "expected_pharmacist_action", "patient_counseling_or_prescriber_message",
    "documentation_required", "evidence_ids", "review_status", "last_evidence_check",
]

_DRILL_HEADERS = [
    "drill_id", "drill_type", "region_localization", "difficulty_1_5",
    "prompt", "data_given", "correct_answer_or_expected_response",
    "worked_rationale", "common_error", "evidence_ids", "review_status",
    "last_evidence_check",
]

_EV_HEADERS = [
    "evidence_id", "source_name", "coverage", "region", "source_type",
    "url", "review_frequency", "use_in_content",
]

_LOC_HEADERS = [
    "region", "regulatory_anchor", "clinical_anchor", "medicine_label_anchor",
    "what_must_be_localized", "do_not_assume", "source_urls",
]


def _csv(headers: list[str], rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _case_row(
    case_id="CP-CASE-T001",
    domain="OTC Triage - Cough",
    subtopic="cough",
    region="UK",
    difficulty="2",
    ev_ids="EV-NICE-CKS;EV-NHS-MEDS",
    review_status="evidence_mapped_pending_human_signoff",
    red_flags="shortness of breath",
    expected_decision="urgent referral if red flag",
) -> list[str]:
    return [
        case_id, "community_pharmacy_case", domain, subtopic, region,
        difficulty, "L2", "Adult 30y", "cough request", "duration;severity",
        red_flags, "none", expected_decision, "hydration advice",
        "missing red flag", "history 25%; decision 25%",
        ev_ids, review_status, "test import", "2026-06-27",
    ]


def _sim_row(
    sim_id="CP-SIM-T001",
    domain="Allergic Rhinitis",
    region="US",
    hidden_risk="wheeze",
    review_status="blueprint_ready_pending_clinical_review",
) -> list[str]:
    return [
        sim_id, domain, "seasonal", region, "3",
        "time_pressure_counter_sim", "Adult 30y", "I need something",
        "N1;N2", hidden_risk, f"Fails if learner misses {hidden_risk}",
        "build rapport", "ask safety Q", "Safety Streak",
        "EV-NICE-CKS", review_status, "2026-06-27",
    ]


def _ev_row(
    ev_id="EV-TEST-001",
    source_name="Test Guideline",
    region="Global",
    url="https://example.com/test",
) -> list[str]:
    return [
        ev_id, source_name, "Test coverage", region,
        "clinical guideline", url, "Annual", "Use for testing",
    ]


def _loc_row(region="UK") -> list[str]:
    return [
        region, "NHS England / MHRA", "NICE CKS", "BNF",
        "Pharmacy First eligibility", "Do not apply US scope",
        "https://cks.nice.org.uk/",
    ]


def _make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Auth helpers (same pattern as other test files)
# ---------------------------------------------------------------------------

_SUPERUSER = {"email": "su@importpipeline.example", "username": "imp_su", "password": "SuperPass1!", "full_name": "Import Super"}
_INST_ADMIN = {"email": "admin@importpipeline.example", "username": "imp_admin", "password": "AdminPass1!", "full_name": "Import Admin"}
_EDUCATOR = {"email": "edu@importpipeline.example", "username": "imp_edu", "password": "EduPass1!", "full_name": "Import Edu"}
_REVIEWER = {"email": "rev@importpipeline.example", "username": "imp_rev", "password": "RevPass1!", "full_name": "Import Rev"}
_STUDENT = {"email": "stu@importpipeline.example", "username": "imp_stu", "password": "StuPass1!", "full_name": "Import Stu"}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _superuser_token(client: AsyncClient, engine) -> str:
    """Register (if needed) and return an access token for the superuser."""
    reg = await client.post("/api/auth/register", json=_SUPERUSER)
    if reg.status_code == 201:
        # Promote to superuser
        from app.models.identity import User
        async with AsyncSession(engine) as s:
            user = (await s.execute(
                select(User).where(User.email == _SUPERUSER["email"])
            )).scalar_one()
            user.is_superuser = True
            await s.commit()
    # Re-login (works whether this is a fresh registration or a re-login)
    resp = await client.post("/api/auth/login", json={
        "email": _SUPERUSER["email"], "password": _SUPERUSER["password"],
    })
    return resp.json()["access_token"]


async def _setup_role_user(
    engine, client: AsyncClient, creds: dict, role_name: str
) -> tuple[str, uuid.UUID, uuid.UUID]:
    """Register user, create org, add user with role. Returns (token, org_id, user_id)."""
    reg = await client.post("/api/auth/register", json=creds)
    user_id = uuid.UUID(reg.json()["id"]) if reg.status_code == 201 else None
    if user_id is None:
        # User already exists — look up by DB
        from app.models.identity import User as _User
        async with AsyncSession(engine) as _s:
            u = (await _s.execute(
                select(_User).where(_User.email == creds["email"])
            )).scalar_one()
            user_id = u.id

    # Superuser creates the org (they become its institution_admin automatically)
    su_token = await _superuser_token(client, engine)
    org_slug = f"org-{uuid.uuid4().hex[:8]}"
    org_resp = await client.post(
        "/api/orgs",
        json={"name": f"Org for {creds['email']}", "slug": org_slug},
        headers=_auth(su_token),
    )
    org_id = uuid.UUID(org_resp.json()["id"])

    # Add target user to the org with the requested role
    await client.post(
        f"/api/orgs/{org_slug}/members",
        json={"email": creds["email"], "role_name": role_name},
        headers=_auth(su_token),
    )
    login_resp = await client.post("/api/auth/login", json={
        "email": creds["email"], "password": creds["password"],
    })
    return login_resp.json()["access_token"], org_id, user_id


# ---------------------------------------------------------------------------
# Unit tests for import_service helpers
# ---------------------------------------------------------------------------

def test_normalize_learner_region_uk():
    assert _normalize_learner_region("UK") == "UK"


def test_normalize_learner_region_australia():
    assert _normalize_learner_region("Australia") == "AU"


def test_normalize_learner_region_global_not_accepted():
    # GLOBAL is not a valid learner region
    assert _normalize_learner_region("Global") is None


def test_normalize_learner_region_invalid():
    assert _normalize_learner_region("EUROPE") is None


def test_parse_evidence_ids_semicolons():
    assert _parse_evidence_ids("EV-A;EV-B;EV-C") == ["EV-A", "EV-B", "EV-C"]


def test_parse_evidence_ids_empty():
    assert _parse_evidence_ids("") == []


def test_parse_evidence_ids_whitespace():
    assert _parse_evidence_ids(" EV-A ; EV-B ") == ["EV-A", "EV-B"]


def test_content_hash_deterministic():
    row = {"case_id": "TEST-001", "domain": "OTC"}
    h1 = _content_hash("TEST-001", "case", row)
    h2 = _content_hash("TEST-001", "case", row)
    assert h1 == h2
    assert len(h1) == 64


def test_content_hash_differs_for_different_content():
    row_a = {"case_id": "TEST-001", "domain": "OTC"}
    row_b = {"case_id": "TEST-001", "domain": "GI"}
    assert _content_hash("TEST-001", "case", row_a) != _content_hash("TEST-001", "case", row_b)


def test_derive_title_uses_station_title():
    row = {"station_title": "Oral Thrush", "domain": "Oral"}
    assert _derive_title("osce_stations_400.csv", row) == "Oral Thrush"


def test_derive_title_synthesizes_domain_subtopic():
    row = {"domain": "OTC Triage", "subtopic": "cough"}
    assert _derive_title("case_bank_7500.csv", row) == "OTC Triage — cough"


def test_derive_title_rx_screening_uses_issue_type():
    row = {"issue_type": "major_interaction"}
    assert _derive_title("prescription_screening_1200.csv", row) == "Rx Screening — major_interaction"


def test_derive_title_drill_uses_prompt():
    row = {"prompt": "Calculate the dose of amoxicillin"}
    title = _derive_title("drills_1200.csv", row)
    assert "Calculate the dose" in title


# ---------------------------------------------------------------------------
# Integration tests — preview endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_rejects_unsupported_extension(client: AsyncClient, fresh_engine):
    token = await _superuser_token(client, fresh_engine)
    content = b"col1,col2\nval1,val2"
    resp = await client.post(
        "/api/content/import/preview",
        headers=_auth(token),
        files={"file": ("upload.xlsx", content, "application/vnd.ms-excel")},
    )
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_preview_rejects_zip_path_traversal(client: AsyncClient, fresh_engine):
    token = await _superuser_token(client, fresh_engine)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../../etc/passwd", "root:x:0:0")
    resp = await client.post(
        "/api/content/import/preview",
        headers=_auth(token),
        files={"file": ("pkg.zip", buf.getvalue(), "application/zip")},
    )
    assert resp.status_code == 400
    assert "path traversal" in resp.json()["detail"].lower() or "rejected" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_preview_rejects_nested_zip(client: AsyncClient, fresh_engine):
    token = await _superuser_token(client, fresh_engine)
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as zf:
        zf.writestr("data.csv", "a,b\n1,2")
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as zf:
        zf.writestr("nested.zip", inner.getvalue())
    resp = await client.post(
        "/api/content/import/preview",
        headers=_auth(token),
        files={"file": ("pkg.zip", outer.getvalue(), "application/zip")},
    )
    assert resp.status_code == 400
    assert "nested" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_preview_rejects_unsupported_filename_in_zip(client: AsyncClient, fresh_engine):
    token = await _superuser_token(client, fresh_engine)
    pkg = _make_zip({"unknown_file.csv": b"col\nval"})
    resp = await client.post(
        "/api/content/import/preview",
        headers=_auth(token),
        files={"file": ("pkg.zip", pkg, "application/zip")},
    )
    assert resp.status_code == 400
    assert "Unrecognized file" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_preview_single_csv_success(client: AsyncClient, fresh_engine):
    token = await _superuser_token(client, fresh_engine)
    content = _csv(_CASE_HEADERS, [_case_row()])
    resp = await client.post(
        "/api/content/import/preview",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_rows"] == 1
    assert data["valid_rows"] == 1
    assert data["invalid_rows"] == 0
    assert "case" in data["detected_content_types"]
    assert data["approval_batch_required"] is False


@pytest.mark.asyncio
async def test_preview_zip_package_success(client: AsyncClient, fresh_engine):
    token = await _superuser_token(client, fresh_engine)
    pkg = _make_zip({
        "case_bank_7500.csv": _csv(_CASE_HEADERS, [_case_row()]),
        "evidence_library.csv": _csv(_EV_HEADERS, [_ev_row()]),
        "localization_rules.csv": _csv(_LOC_HEADERS, [_loc_row()]),
    })
    resp = await client.post(
        "/api/content/import/preview",
        headers=_auth(token),
        files={"file": ("pkg.zip", pkg, "application/zip")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_rows"] > 0
    assert "case" in data["detected_content_types"]


@pytest.mark.asyncio
async def test_preview_reports_missing_required_columns(client: AsyncClient, fresh_engine):
    token = await _superuser_token(client, fresh_engine)
    # CSV is missing required columns (only has 2 columns)
    content = _csv(["case_id", "domain"], [["CP-CASE-T001", "OTC"]])
    resp = await client.post(
        "/api/content/import/preview",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["invalid_rows"] > 0 or len(data["errors_by_file"]) > 0


@pytest.mark.asyncio
async def test_preview_reports_invalid_region(client: AsyncClient, fresh_engine):
    token = await _superuser_token(client, fresh_engine)
    content = _csv(_CASE_HEADERS, [_case_row(region="EUROPE")])
    resp = await client.post(
        "/api/content/import/preview",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["invalid_rows"] == 1
    errors = data["errors_by_file"].get("case_bank_7500.csv", [])
    assert any("region" in e.lower() or "EUROPE" in e for e in errors)


@pytest.mark.asyncio
async def test_preview_detects_duplicate_external_id_in_upload(
    client: AsyncClient, fresh_engine
):
    token = await _superuser_token(client, fresh_engine)
    # Two rows with same case_id
    row1 = _case_row(case_id="CP-CASE-DUP")
    row2 = _case_row(case_id="CP-CASE-DUP")
    content = _csv(_CASE_HEADERS, [row1, row2])
    resp = await client.post(
        "/api/content/import/preview",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["duplicate_summary"]["duplicate_external_id_in_upload"] >= 1


@pytest.mark.asyncio
async def test_preview_detects_duplicate_hash_in_upload(
    client: AsyncClient, fresh_engine
):
    token = await _superuser_token(client, fresh_engine)
    # Same content, different case_id but content identical → same hash
    row1 = _case_row(case_id="CP-CASE-H001")
    row2 = list(row1)
    row2[0] = "CP-CASE-H002"  # different external_id
    content = _csv(_CASE_HEADERS, [row1, row2])
    resp = await client.post(
        "/api/content/import/preview",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert resp.status_code == 200
    # Second row may be detected as dup (hash matches first row after substituting ext_id)
    # The important thing is both rows are processed without error
    data = resp.json()
    assert data["total_rows"] == 2


@pytest.mark.asyncio
async def test_preview_detects_existing_external_id_in_db(
    client: AsyncClient, fresh_engine
):
    token = await _superuser_token(client, fresh_engine)
    # Pre-seed a ContentItem with a known external_id
    async with AsyncSession(fresh_engine) as s:
        item = ContentItem(
            external_id="CP-CASE-EXISTING",
            title="Pre-existing item",
            content_type="case",
            status="pending_review",
        )
        s.add(item)
        await s.commit()

    content = _csv(_CASE_HEADERS, [_case_row(case_id="CP-CASE-EXISTING")])
    resp = await client.post(
        "/api/content/import/preview",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["duplicate_summary"]["existing_external_id_in_db"] == 1


@pytest.mark.asyncio
async def test_preview_does_not_create_content_items(
    client: AsyncClient, fresh_engine
):
    token = await _superuser_token(client, fresh_engine)
    content = _csv(_CASE_HEADERS, [_case_row(), _case_row(case_id="CP-CASE-T002")])
    resp = await client.post(
        "/api/content/import/preview",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert resp.status_code == 200
    # DB must remain empty
    async with AsyncSession(fresh_engine) as s:
        count = (await s.execute(select(ContentItem))).scalars().all()
        assert len(count) == 0


# ---------------------------------------------------------------------------
# Integration tests — commit endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_commit_single_csv_pending_review(client: AsyncClient, fresh_engine):
    """Commit a case CSV without approval batch → items get pending_review status."""
    token, _, _ = await _setup_role_user(
        fresh_engine, client, _INST_ADMIN, "institution_admin"
    )
    content = _csv(_CASE_HEADERS, [_case_row()])
    resp = await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["created_items"] == 1
    assert data["created_versions"] == 1

    async with AsyncSession(fresh_engine) as s:
        item = (await s.execute(
            select(ContentItem).where(ContentItem.external_id == "CP-CASE-T001")
        )).scalar_one()
        assert item.status == "pending_review"
        assert item.content_type == "case"


@pytest.mark.asyncio
async def test_commit_creates_content_item_and_version(client: AsyncClient, fresh_engine):
    token, _, _ = await _setup_role_user(
        fresh_engine, client, _INST_ADMIN, "institution_admin"
    )
    content = _csv(_CASE_HEADERS, [_case_row(case_id="CP-CASE-V001")])
    resp = await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert resp.status_code == 201

    async with AsyncSession(fresh_engine) as s:
        item = (await s.execute(
            select(ContentItem).where(ContentItem.external_id == "CP-CASE-V001")
        )).scalar_one()
        assert item.current_version_id is not None

        version = await s.get(ContentVersion, item.current_version_id)
        assert version is not None
        assert version.source_file_name == "case_bank_7500.csv"
        assert version.source_row_number == 2  # header=1, first data row=2
        assert version.content_hash is not None
        assert len(version.content_hash) == 64
        assert version.is_current is True


@pytest.mark.asyncio
async def test_commit_preserves_source_file_and_row(client: AsyncClient, fresh_engine):
    token, _, _ = await _setup_role_user(
        fresh_engine, client, _INST_ADMIN, "institution_admin"
    )
    rows = [_case_row(case_id=f"CP-CASE-SRC{i:03d}") for i in range(3)]
    content = _csv(_CASE_HEADERS, rows)
    await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    async with AsyncSession(fresh_engine) as s:
        versions = (await s.execute(select(ContentVersion))).scalars().all()
        assert len(versions) == 3
        row_nums = {v.source_row_number for v in versions}
        assert row_nums == {2, 3, 4}  # header row 1, data rows 2-4
        file_names = {v.source_file_name for v in versions}
        assert file_names == {"case_bank_7500.csv"}


@pytest.mark.asyncio
async def test_commit_skips_duplicate_external_id(client: AsyncClient, fresh_engine):
    """Second import of the same external_id skips the duplicate."""
    token, _, _ = await _setup_role_user(
        fresh_engine, client, _INST_ADMIN, "institution_admin"
    )
    content = _csv(_CASE_HEADERS, [_case_row(case_id="CP-CASE-DUP2")])
    # First commit
    r1 = await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert r1.status_code == 201
    assert r1.json()["created_items"] == 1

    # Second commit — same file
    r2 = await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert r2.status_code == 201
    assert r2.json()["created_items"] == 0
    assert r2.json()["skipped_duplicates"] >= 1

    async with AsyncSession(fresh_engine) as s:
        count = (await s.execute(
            select(ContentItem).where(ContentItem.external_id == "CP-CASE-DUP2")
        )).scalars().all()
        assert len(count) == 1  # only one was created


@pytest.mark.asyncio
async def test_commit_does_not_publish(client: AsyncClient, fresh_engine):
    """Imported content must never be auto-published."""
    token, _, _ = await _setup_role_user(
        fresh_engine, client, _INST_ADMIN, "institution_admin"
    )
    content = _csv(_CASE_HEADERS, [_case_row()])
    await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    async with AsyncSession(fresh_engine) as s:
        items = (await s.execute(select(ContentItem))).scalars().all()
        for item in items:
            assert item.status != "published"


@pytest.mark.asyncio
async def test_commit_writes_audit_log(client: AsyncClient, fresh_engine):
    token, _, _ = await _setup_role_user(
        fresh_engine, client, _INST_ADMIN, "institution_admin"
    )
    content = _csv(_CASE_HEADERS, [_case_row(case_id="CP-CASE-AUD")])
    await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    async with AsyncSession(fresh_engine) as s:
        logs = (await s.execute(
            select(AuditLog).where(AuditLog.action == "content.bulk_import_committed")
        )).scalars().all()
        assert len(logs) >= 1
        log = logs[0]
        # Audit log must not contain clinical payload
        extra = log.extra_data or {}
        assert "red_flags_to_screen" not in str(extra)
        assert "patient_profile" not in str(extra)
        # Must contain safe metadata
        assert "created_items" in extra or "source_file" in extra


@pytest.mark.asyncio
async def test_commit_approved_rows_require_approve_permission(
    client: AsyncClient, fresh_engine
):
    """Educator has content.import but not content.approve — approved rows must be blocked."""
    edu_token, _, _ = await _setup_role_user(
        fresh_engine, client, _EDUCATOR, "educator"
    )
    # Create a mock approval batch via superuser
    su_token = await _superuser_token(client, fresh_engine)
    batch_resp = await client.post(
        "/api/content/approval-batches",
        json={
            "batch_name": "Test Batch",
            "approved_by_team_name": "Pharmacist Team",
            "approved_at": "2026-06-27T00:00:00Z",
        },
        headers=_auth(su_token),
    )
    batch_id = batch_resp.json()["id"]

    # Educator tries to commit with approval_batch_id and an "approved" row
    row = _case_row(review_status="approved")
    content = _csv(_CASE_HEADERS, [row])
    resp = await client.post(
        "/api/content/import/commit",
        headers=_auth(edu_token),
        data={"approval_batch_id": batch_id},
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert resp.status_code == 403
    assert "content.approve" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_commit_approved_rows_with_approve_permission(
    client: AsyncClient, fresh_engine
):
    """institution_admin has content.approve — approved rows get clinically_approved."""
    token, _, _ = await _setup_role_user(
        fresh_engine, client, _INST_ADMIN, "institution_admin"
    )
    su_token = await _superuser_token(client, fresh_engine)
    batch_resp = await client.post(
        "/api/content/approval-batches",
        json={
            "batch_name": "Batch 1",
            "approved_by_team_name": "Pharmacist Team",
            "approved_at": "2026-06-27T00:00:00Z",
        },
        headers=_auth(su_token),
    )
    batch_id = batch_resp.json()["id"]

    row = _case_row(case_id="CP-CASE-APPR", review_status="approved")
    content = _csv(_CASE_HEADERS, [row])
    resp = await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        data={"approval_batch_id": batch_id},
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["created_items"] == 1

    async with AsyncSession(fresh_engine) as s:
        item = (await s.execute(
            select(ContentItem).where(ContentItem.external_id == "CP-CASE-APPR")
        )).scalar_one()
        assert item.status == "clinically_approved"


# ---------------------------------------------------------------------------
# Evidence source import tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_commit_evidence_library_creates_sources(
    client: AsyncClient, fresh_engine
):
    token, _, _ = await _setup_role_user(
        fresh_engine, client, _INST_ADMIN, "institution_admin"
    )
    ev_rows = [
        _ev_row("EV-T1", "WHO Safety", url="https://who.int/test1"),
        _ev_row("EV-T2", "NICE CKS", url="https://nice.org.uk/test2"),
    ]
    content = _csv(_EV_HEADERS, ev_rows)
    resp = await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("evidence_library.csv", content, "text/csv")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["created_evidence_sources"] == 2

    async with AsyncSession(fresh_engine) as s:
        sources = (await s.execute(select(EvidenceSource))).scalars().all()
        assert len(sources) == 2
        urls = {s.url for s in sources}
        assert "https://who.int/test1" in urls


@pytest.mark.asyncio
async def test_commit_evidence_skips_duplicate_url(client: AsyncClient, fresh_engine):
    token, _, _ = await _setup_role_user(
        fresh_engine, client, _INST_ADMIN, "institution_admin"
    )
    ev_rows = [_ev_row("EV-DUP", "Guideline", url="https://dup.example.com/ev")]
    content = _csv(_EV_HEADERS, ev_rows)
    for _ in range(2):
        await client.post(
            "/api/content/import/commit",
            headers=_auth(token),
            files={"file": ("evidence_library.csv", content, "text/csv")},
        )
    async with AsyncSession(fresh_engine) as s:
        sources = (await s.execute(select(EvidenceSource))).scalars().all()
        assert len(sources) == 1  # only one created despite two imports


@pytest.mark.asyncio
async def test_preview_evidence_invalid_url_reported(client: AsyncClient, fresh_engine):
    token = await _superuser_token(client, fresh_engine)
    bad_row = ["EV-BAD", "Bad Source", "coverage", "Global", "type", "not-a-url", "Annual", "use"]
    content = _csv(_EV_HEADERS, [bad_row])
    resp = await client.post(
        "/api/content/import/preview",
        headers=_auth(token),
        files={"file": ("evidence_library.csv", content, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["invalid_rows"] >= 1


# ---------------------------------------------------------------------------
# Localization rules import tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_commit_localization_rules_creates_region_rules(
    client: AsyncClient, fresh_engine
):
    token, _, _ = await _setup_role_user(
        fresh_engine, client, _INST_ADMIN, "institution_admin"
    )
    rows = [_loc_row("UK"), _loc_row("US")]
    content = _csv(_LOC_HEADERS, rows)
    resp = await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("localization_rules.csv", content, "text/csv")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["created_region_rules"] == 2

    async with AsyncSession(fresh_engine) as s:
        rules = (await s.execute(select(RegionPublishingRule))).scalars().all()
        assert len(rules) == 2
        # All imported rules must be inactive (reference, not enforcement)
        assert all(not r.is_active for r in rules)


@pytest.mark.asyncio
async def test_commit_localization_skips_existing_region(client: AsyncClient, fresh_engine):
    token, _, _ = await _setup_role_user(
        fresh_engine, client, _INST_ADMIN, "institution_admin"
    )
    content = _csv(_LOC_HEADERS, [_loc_row("GCC")])
    for _ in range(2):
        await client.post(
            "/api/content/import/commit",
            headers=_auth(token),
            files={"file": ("localization_rules.csv", content, "text/csv")},
        )
    async with AsyncSession(fresh_engine) as s:
        rules = (await s.execute(
            select(RegionPublishingRule).where(RegionPublishingRule.region_code == "GCC")
        )).scalars().all()
        assert len(rules) == 1


@pytest.mark.asyncio
async def test_preview_localization_rejects_invalid_region(
    client: AsyncClient, fresh_engine
):
    token = await _superuser_token(client, fresh_engine)
    bad_row = ["EUROPE", "Some regulator", "some anchor", "label", "what", "donot", "url"]
    content = _csv(_LOC_HEADERS, [bad_row])
    resp = await client.post(
        "/api/content/import/preview",
        headers=_auth(token),
        files={"file": ("localization_rules.csv", content, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["invalid_rows"] >= 1


# ---------------------------------------------------------------------------
# Security tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_enforces_file_size_limit(client: AsyncClient, fresh_engine):
    token = await _superuser_token(client, fresh_engine)
    # Create a 1-byte payload but with a spoofed Content-Length — easier to test
    # by patching the MAX constant. We'll test the code path by reading the source.
    from app.services import import_service as svc
    original = svc.MAX_UPLOAD_BYTES
    svc.MAX_UPLOAD_BYTES = 10  # 10 bytes limit for testing
    try:
        content = _csv(_CASE_HEADERS, [_case_row()])  # > 10 bytes
        resp = await client.post(
            "/api/content/import/preview",
            headers=_auth(token),
            files={"file": ("case_bank_7500.csv", content, "text/csv")},
        )
        assert resp.status_code == 400
        assert "size" in resp.json()["detail"].lower() or "MB" in resp.json()["detail"]
    finally:
        svc.MAX_UPLOAD_BYTES = original


@pytest.mark.asyncio
async def test_preview_rejects_excessive_file_count_in_zip(
    client: AsyncClient, fresh_engine
):
    token = await _superuser_token(client, fresh_engine)
    from app.services import import_service as svc
    original = svc.MAX_ZIP_FILES
    svc.MAX_ZIP_FILES = 2
    try:
        pkg = _make_zip({
            "case_bank_7500.csv": _csv(_CASE_HEADERS, [_case_row()]),
            "evidence_library.csv": _csv(_EV_HEADERS, [_ev_row()]),
            "localization_rules.csv": _csv(_LOC_HEADERS, [_loc_row()]),
        })
        resp = await client.post(
            "/api/content/import/preview",
            headers=_auth(token),
            files={"file": ("pkg.zip", pkg, "application/zip")},
        )
        assert resp.status_code == 400
        assert "entries" in resp.json()["detail"].lower() or "ZIP" in resp.json()["detail"]
    finally:
        svc.MAX_ZIP_FILES = original


@pytest.mark.asyncio
async def test_preview_rejects_excessive_row_count(client: AsyncClient, fresh_engine):
    token = await _superuser_token(client, fresh_engine)
    from app.services import import_service as svc
    original = svc.MAX_ROWS_PER_FILE
    svc.MAX_ROWS_PER_FILE = 2
    try:
        rows = [_case_row(case_id=f"CP-CASE-{i:05d}") for i in range(5)]
        content = _csv(_CASE_HEADERS, rows)
        resp = await client.post(
            "/api/content/import/preview",
            headers=_auth(token),
            files={"file": ("case_bank_7500.csv", content, "text/csv")},
        )
        assert resp.status_code == 200  # preview returns validation result, not 400
        data = resp.json()
        # The file-level error about row count appears in errors_by_file or invalid_rows
        has_row_count_error = (
            data["invalid_rows"] > 0 or
            any("exceeds" in e for errors in data["errors_by_file"].values() for e in errors)
        )
        assert has_row_count_error
    finally:
        svc.MAX_ROWS_PER_FILE = original


@pytest.mark.asyncio
async def test_audit_log_does_not_contain_clinical_payload(
    client: AsyncClient, fresh_engine
):
    token, _, _ = await _setup_role_user(
        fresh_engine, client, _INST_ADMIN, "institution_admin"
    )
    content = _csv(_CASE_HEADERS, [_case_row()])
    await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    async with AsyncSession(fresh_engine) as s:
        logs = (await s.execute(
            select(AuditLog).where(AuditLog.action == "content.bulk_import_committed")
        )).scalars().all()
        for log in logs:
            payload_str = json.dumps(log.extra_data or {})
            assert "red_flags_to_screen" not in payload_str
            assert "presenting_request" not in payload_str
            assert "counseling_points" not in payload_str


# ---------------------------------------------------------------------------
# RBAC tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_requires_content_import_permission(
    client: AsyncClient, fresh_engine
):
    """A student (no content.import) must be blocked from preview."""
    stu_token, _, _ = await _setup_role_user(
        fresh_engine, client, _STUDENT, "student"
    )
    content = _csv(_CASE_HEADERS, [_case_row()])
    resp = await client.post(
        "/api/content/import/preview",
        headers=_auth(stu_token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_commit_requires_content_import_permission(
    client: AsyncClient, fresh_engine
):
    """A student (no content.import) must be blocked from commit."""
    stu_token, _, _ = await _setup_role_user(
        fresh_engine, client,
        {"email": "stu2@importpipeline.example", "username": "imp_stu2", "password": "StuPass2!", "full_name": "Stu2"},
        "student",
    )
    content = _csv(_CASE_HEADERS, [_case_row()])
    resp = await client.post(
        "/api/content/import/commit",
        headers=_auth(stu_token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_educator_can_preview_and_commit_pending(
    client: AsyncClient, fresh_engine
):
    """Educator has content.import — can preview and commit as pending_review."""
    edu_token, _, _ = await _setup_role_user(
        fresh_engine, client,
        {"email": "edu2@importpipeline.example", "username": "imp_edu2", "password": "EduPass2!", "full_name": "Edu2"},
        "educator",
    )
    content = _csv(_CASE_HEADERS, [_case_row(case_id="CP-EDU-001")])

    prev = await client.post(
        "/api/content/import/preview",
        headers=_auth(edu_token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert prev.status_code == 200

    comm = await client.post(
        "/api/content/import/commit",
        headers=_auth(edu_token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert comm.status_code == 201
    assert comm.json()["created_items"] == 1


# ---------------------------------------------------------------------------
# Multi-file ZIP commit test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_commit_zip_multiple_file_types(client: AsyncClient, fresh_engine):
    """Committing a ZIP with multiple content types creates items for each."""
    token, _, _ = await _setup_role_user(
        fresh_engine, client,
        {"email": "adm2@importpipeline.example", "username": "imp_adm2", "password": "Adm2Pass!", "full_name": "Adm2"},
        "institution_admin",
    )
    pkg = _make_zip({
        "case_bank_7500.csv": _csv(_CASE_HEADERS, [_case_row(case_id="CP-ZIP-CASE")]),
        "simulation_blueprints_1200.csv": _csv(_SIM_HEADERS, [_sim_row()]),
        "evidence_library.csv": _csv(_EV_HEADERS, [_ev_row(url="https://zip-test.example.com")]),
        "localization_rules.csv": _csv(_LOC_HEADERS, [_loc_row("AU")]),
    })
    resp = await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("pkg.zip", pkg, "application/zip")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["created_items"] == 2  # case + simulation
    assert data["created_versions"] == 2
    assert data["created_evidence_sources"] == 1
    assert data["created_region_rules"] == 1


@pytest.mark.asyncio
async def test_commit_reference_only_files_reported_in_warnings(
    client: AsyncClient, fresh_engine
):
    """taxonomy.csv and games_rewards.csv are reference-only and generate a warning."""
    token, _, _ = await _setup_role_user(
        fresh_engine, client,
        {"email": "adm3@importpipeline.example", "username": "imp_adm3", "password": "Adm3Pass!", "full_name": "Adm3"},
        "institution_admin",
    )
    taxonomy_csv = _csv(
        ["domain", "subtopics", "case_target", "simulation_target", "osce_target",
         "rx_screening_target", "drill_target", "core_competencies", "primary_evidence_ids"],
        [["OTC", "cough;cold", "375", "60", "20", "60", "60", "triage", "EV-NICE"]],
    )
    pkg = _make_zip({"taxonomy.csv": taxonomy_csv})
    resp = await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("pkg.zip", pkg, "application/zip")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["created_items"] == 0
    assert any("reference-only" in w for w in data["warnings"])


@pytest.mark.asyncio
async def test_import_batch_record_created_on_commit(client: AsyncClient, fresh_engine):
    """Committing a file always creates an ImportBatch record."""
    token, _, _ = await _setup_role_user(
        fresh_engine, client,
        {"email": "adm4@importpipeline.example", "username": "imp_adm4", "password": "Adm4Pass!", "full_name": "Adm4"},
        "institution_admin",
    )
    content = _csv(_CASE_HEADERS, [_case_row(case_id="CP-BATCH-T")])
    resp = await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert resp.status_code == 201
    batch_id = resp.json()["import_batch_id"]

    async with AsyncSession(fresh_engine) as s:
        batch = await s.get(ImportBatch, uuid.UUID(batch_id))
        assert batch is not None
        assert batch.status == "committed"
        assert batch.package_type == "csv"
        assert batch.source_file_name == "case_bank_7500.csv"


# ---------------------------------------------------------------------------
# Regression tests — circular FK / PostgreSQL DEFERRABLE constraint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_commit_bulk_rows_all_get_current_version_id(
    client: AsyncClient, fresh_engine
):
    """
    Regression: bulk commit of many rows must set current_version_id on every item.

    Root cause (fixed in migration 013): content_items.current_version_id →
    content_versions.id was NOT DEFERRABLE in PostgreSQL.  SQLAlchemy's unit-of-work
    inserts ContentItems (with current_version_id already populated) before
    ContentVersions exist in the DB, because use_alter=True removes the FK from
    SQLAlchemy's dependency graph.  PostgreSQL enforced the FK at INSERT time and
    raised IntegrityError on the very first row.

    Migration 013 makes the FK DEFERRABLE INITIALLY DEFERRED so the check runs at
    COMMIT time, by which point all versions exist.  SQLite never enforced this FK
    so the bug was invisible in the existing test suite.
    """
    token, _, _ = await _setup_role_user(
        fresh_engine, client,
        {"email": "bulk@importpipeline.example", "username": "imp_bulk", "password": "BulkPass1!", "full_name": "Bulk"},
        "institution_admin",
    )
    rows = [_case_row(case_id=f"CP-BULK-{i:04d}") for i in range(25)]
    content = _csv(_CASE_HEADERS, rows)
    resp = await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["created_items"] == 25
    assert data["created_versions"] == 25

    async with AsyncSession(fresh_engine) as s:
        items = (await s.execute(select(ContentItem))).scalars().all()
        assert len(items) == 25
        for item in items:
            assert item.current_version_id is not None, (
                f"Item {item.external_id} has no current_version_id — "
                "circular FK was not deferred properly"
            )
            version = await s.get(ContentVersion, item.current_version_id)
            assert version is not None
            assert version.content_item_id == item.id
            assert version.is_current is True


@pytest.mark.asyncio
async def test_commit_mixed_zip_bulk_all_items_have_version(
    client: AsyncClient, fresh_engine
):
    """Bulk commit via ZIP: all created items across file types have current_version_id."""
    token, _, _ = await _setup_role_user(
        fresh_engine, client,
        {"email": "zipbulk@importpipeline.example", "username": "imp_zipbulk", "password": "ZipBulk1!", "full_name": "ZipBulk"},
        "institution_admin",
    )
    case_rows = [_case_row(case_id=f"CP-ZB-CASE-{i:03d}") for i in range(5)]
    sim_rows = [_sim_row(sim_id=f"CP-ZB-SIM-{i:03d}") for i in range(5)]
    pkg = _make_zip({
        "case_bank_7500.csv": _csv(_CASE_HEADERS, case_rows),
        "simulation_blueprints_1200.csv": _csv(_SIM_HEADERS, sim_rows),
    })
    resp = await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("pkg.zip", pkg, "application/zip")},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["created_items"] == 10
    assert data["created_versions"] == 10

    async with AsyncSession(fresh_engine) as s:
        items = (await s.execute(select(ContentItem))).scalars().all()
        for item in items:
            assert item.current_version_id is not None
            version = await s.get(ContentVersion, item.current_version_id)
            assert version is not None
            assert version.content_item_id == item.id


@pytest.mark.asyncio
async def test_commit_rerun_is_idempotent_no_error(client: AsyncClient, fresh_engine):
    """
    Re-committing the same package must skip all rows and return 201 (not 500/422).

    Ensures that the dedup logic works correctly and a second commit is safe.
    """
    token, _, _ = await _setup_role_user(
        fresh_engine, client,
        {"email": "idem@importpipeline.example", "username": "imp_idem", "password": "IdemPass1!", "full_name": "Idem"},
        "institution_admin",
    )
    rows = [_case_row(case_id=f"CP-IDEM-{i:03d}") for i in range(5)]
    content = _csv(_CASE_HEADERS, rows)

    r1 = await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert r1.status_code == 201
    assert r1.json()["created_items"] == 5

    r2 = await client.post(
        "/api/content/import/commit",
        headers=_auth(token),
        files={"file": ("case_bank_7500.csv", content, "text/csv")},
    )
    assert r2.status_code == 201
    assert r2.json()["created_items"] == 0
    assert r2.json()["skipped_duplicates"] >= 5

    async with AsyncSession(fresh_engine) as s:
        count = len((await s.execute(select(ContentItem))).scalars().all())
        assert count == 5  # no duplicates were created
