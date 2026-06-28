"""
Real-package import smoke tests.

These tests load the actual community_pharmacy_mega_content_bank_v2_csv.zip and
run preview/commit against an isolated in-memory SQLite database. They are
automatically skipped when the ZIP is not present (CI and developer machines
without the upload).

IMPORTANT: These tests never write to production. All DB operations use
sqlite+aiosqlite:///:memory: and are discarded after each test.
"""
import os
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.database import Base
from app.models.governance import ContentItem, ContentVersion, EvidenceSource, RegionPublishingRule
from app.models.identity import Permission, Role, RolePermission, User
from app.services.import_service import commit_package, preview_package

# ---------------------------------------------------------------------------
# Locate the real ZIP (best-effort — skip if absent)
# ---------------------------------------------------------------------------
_UPLOAD_DIR = Path("/root/.claude/uploads/a45c7ef9-a7fa-59d9-94d3-f6cb7563b06e")
_ZIP_NAME = "1f73bf05-community_pharmacy_mega_content_bank_v2_csv.zip"
_ZIP_PATH = _UPLOAD_DIR / _ZIP_NAME

_ZIP_MISSING = not _ZIP_PATH.exists()
_SKIP_REASON = "Real content package ZIP not available in this environment"

# ---------------------------------------------------------------------------
# Expected counts from the real package (single source of truth)
# ---------------------------------------------------------------------------
_EXPECTED = {
    "case": 7500,
    "simulation": 1200,
    "osce_station": 400,
    "prescription_screening": 1200,
    "drill": 1200,
    "total_items": 11500,
    "evidence_sources": 20,
    "region_rules": 4,
    "total_valid_rows_preview": 11524,   # includes evidence + loc rules
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
_ROLES = [
    ("student", "Student"),
    ("educator", "Educator"),
    ("content_reviewer", "Content Reviewer"),
    ("institution_admin", "Institution Administrator"),
    ("platform_admin", "Platform Administrator"),
]

_PERMISSIONS = [
    ("content.import", "Import Content", "content", "import"),
    ("content.review", "Review Content", "content", "review"),
    ("content.approve", "Approve Content", "content", "approve"),
    ("content.publish", "Publish Content", "content", "publish"),
    ("content.unpublish", "Unpublish Content", "content", "unpublish"),
    ("content.version.create", "Create Content Version", "content", "version.create"),
    ("content.rollback", "Rollback Content Version", "content", "rollback"),
    ("evidence.manage", "Manage Evidence Sources", "evidence", "manage"),
    ("analytics.view", "View Analytics", "analytics", "view"),
    ("analytics.view_org", "View Organization Analytics", "analytics", "view_org"),
]


@pytest_asyncio.fixture
async def real_pkg_engine():
    """Per-test isolated in-memory engine with governance tables and seeded roles."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as s:
        role_objs = {}
        for name, display_name in _ROLES:
            r = Role(name=name, display_name=display_name, is_system_role=True)
            s.add(r)
            role_objs[name] = r
        await s.flush()

        perm_objs = {}
        for perm_name, display_name, resource, action in _PERMISSIONS:
            p = Permission(name=perm_name, display_name=display_name, resource=resource, action=action)
            s.add(p)
            perm_objs[perm_name] = p
        await s.flush()

        await s.commit()

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def real_pkg_actor(real_pkg_engine):
    """Superuser actor for import operations."""
    SessionLocal = async_sessionmaker(
        bind=real_pkg_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with SessionLocal() as s:
        actor = User(
            email="pkgtest@importpipeline.example",
            username="pkgtest",
            hashed_password=hash_password("RealPkg123!"),
            full_name="Package Test Actor",
            is_active=True,
            is_superuser=True,
        )
        s.add(actor)
        await s.commit()
        await s.refresh(actor)
    return actor


@pytest_asyncio.fixture
async def real_pkg_session(real_pkg_engine):
    """Async session for the isolated test engine."""
    SessionLocal = async_sessionmaker(
        bind=real_pkg_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with SessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_ZIP_MISSING, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_real_package_preview_clean(real_pkg_session):
    """Full preview of the real ZIP returns zero errors and expected row counts."""
    zip_bytes = _ZIP_PATH.read_bytes()
    result = await preview_package(zip_bytes, _ZIP_NAME, real_pkg_session)

    assert result.invalid_rows == 0, f"Unexpected invalid rows: {result.row_errors[:5]}"
    assert result.errors_by_file == {}, f"File errors: {result.errors_by_file}"
    assert result.valid_rows == _EXPECTED["total_valid_rows_preview"]
    assert result.duplicate_summary.duplicate_external_id_in_upload == 0
    assert result.duplicate_summary.duplicate_hash_in_upload == 0
    assert result.duplicate_summary.existing_external_id_in_db == 0
    assert result.duplicate_summary.existing_hash_in_db == 0
    assert sorted(result.detected_content_types) == sorted([
        "case", "drill", "osce_station", "prescription_screening", "simulation"
    ])


@pytest.mark.skipif(_ZIP_MISSING, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_real_package_commit_counts(real_pkg_engine, real_pkg_actor):
    """Commit creates the expected number of governance records."""
    SessionLocal = async_sessionmaker(
        bind=real_pkg_engine, class_=AsyncSession, expire_on_commit=False
    )
    zip_bytes = _ZIP_PATH.read_bytes()

    async with SessionLocal() as session:
        result = await commit_package(
            file_bytes=zip_bytes,
            file_name=_ZIP_NAME,
            db=session,
            actor=real_pkg_actor,
            approval_batch_id=None,
            has_approve_permission=False,
        )

    assert result.created_items == _EXPECTED["total_items"]
    assert result.created_versions == _EXPECTED["total_items"]
    assert result.created_evidence_sources == _EXPECTED["evidence_sources"]
    assert result.created_region_rules == _EXPECTED["region_rules"]
    assert result.skipped_duplicates == 0
    assert result.invalid_rows == 0

    # Verify DB record counts
    async with SessionLocal() as session:
        items = (await session.execute(select(func.count(ContentItem.id)))).scalar()
        versions = (await session.execute(select(func.count(ContentVersion.id)))).scalar()
        evidence = (await session.execute(select(func.count(EvidenceSource.id)))).scalar()
        rules = (await session.execute(select(func.count(RegionPublishingRule.id)))).scalar()

    assert items == _EXPECTED["total_items"]
    assert versions == _EXPECTED["total_items"]
    assert evidence == _EXPECTED["evidence_sources"]
    assert rules == _EXPECTED["region_rules"]


@pytest.mark.skipif(_ZIP_MISSING, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_real_package_no_autopublish(real_pkg_engine, real_pkg_actor):
    """Imported content must never land in 'published' status."""
    SessionLocal = async_sessionmaker(
        bind=real_pkg_engine, class_=AsyncSession, expire_on_commit=False
    )
    zip_bytes = _ZIP_PATH.read_bytes()

    async with SessionLocal() as session:
        await commit_package(
            file_bytes=zip_bytes,
            file_name=_ZIP_NAME,
            db=session,
            actor=real_pkg_actor,
            approval_batch_id=None,
            has_approve_permission=False,
        )

    async with SessionLocal() as session:
        published = (
            await session.execute(
                select(func.count(ContentItem.id)).where(ContentItem.status == "published")
            )
        ).scalar()
        assert published == 0, "Auto-publish violation: imported content must never be published"

        pending = (
            await session.execute(
                select(func.count(ContentItem.id)).where(ContentItem.status == "pending_review")
            )
        ).scalar()
        assert pending == _EXPECTED["total_items"]


@pytest.mark.skipif(_ZIP_MISSING, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_real_package_all_review_status_pending(real_pkg_engine, real_pkg_actor):
    """All review_status values in this package are pending — no items become clinically_approved."""
    import uuid as _uuid
    SessionLocal = async_sessionmaker(
        bind=real_pkg_engine, class_=AsyncSession, expire_on_commit=False
    )
    zip_bytes = _ZIP_PATH.read_bytes()

    # Even with has_approve_permission=True and an approval_batch_id, no items
    # should become clinically_approved because all review_status values are pending.
    fake_batch_id = _uuid.uuid4()

    async with SessionLocal() as session:
        result = await commit_package(
            file_bytes=zip_bytes,
            file_name=_ZIP_NAME,
            db=session,
            actor=real_pkg_actor,
            approval_batch_id=fake_batch_id,
            has_approve_permission=True,
        )

    async with SessionLocal() as session:
        clinically_approved = (
            await session.execute(
                select(func.count(ContentItem.id))
                .where(ContentItem.status == "clinically_approved")
            )
        ).scalar()
        assert clinically_approved == 0, (
            "Expected 0 clinically_approved items — all review_status values in this package "
            "are pending variants, not in _APPROVED_REVIEW_STATUSES"
        )


@pytest.mark.skipif(_ZIP_MISSING, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_real_package_content_type_distribution(real_pkg_engine, real_pkg_actor):
    """Each content type has the expected number of records."""
    SessionLocal = async_sessionmaker(
        bind=real_pkg_engine, class_=AsyncSession, expire_on_commit=False
    )
    zip_bytes = _ZIP_PATH.read_bytes()

    async with SessionLocal() as session:
        await commit_package(
            file_bytes=zip_bytes,
            file_name=_ZIP_NAME,
            db=session,
            actor=real_pkg_actor,
            approval_batch_id=None,
            has_approve_permission=False,
        )

    async with SessionLocal() as session:
        rows = await session.execute(
            select(ContentItem.content_type, func.count(ContentItem.id))
            .group_by(ContentItem.content_type)
        )
        type_counts = {row[0]: row[1] for row in rows}

    for ctype, expected_count in [
        ("case", _EXPECTED["case"]),
        ("simulation", _EXPECTED["simulation"]),
        ("osce_station", _EXPECTED["osce_station"]),
        ("prescription_screening", _EXPECTED["prescription_screening"]),
        ("drill", _EXPECTED["drill"]),
    ]:
        assert type_counts.get(ctype) == expected_count, (
            f"Expected {expected_count} {ctype} items, got {type_counts.get(ctype)}"
        )


@pytest.mark.skipif(_ZIP_MISSING, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_real_package_region_rules_inactive(real_pkg_engine, real_pkg_actor):
    """All imported RegionPublishingRule records must be inactive (is_active=False)."""
    SessionLocal = async_sessionmaker(
        bind=real_pkg_engine, class_=AsyncSession, expire_on_commit=False
    )
    zip_bytes = _ZIP_PATH.read_bytes()

    async with SessionLocal() as session:
        await commit_package(
            file_bytes=zip_bytes,
            file_name=_ZIP_NAME,
            db=session,
            actor=real_pkg_actor,
            approval_batch_id=None,
            has_approve_permission=False,
        )

    async with SessionLocal() as session:
        active_rules = (
            await session.execute(
                select(func.count(RegionPublishingRule.id))
                .where(RegionPublishingRule.is_active == True)
            )
        ).scalar()
        assert active_rules == 0, "Imported region rules must be inactive until admin activates them"


@pytest.mark.skipif(_ZIP_MISSING, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_real_package_duplicate_reimport_skipped(real_pkg_engine, real_pkg_actor):
    """Re-importing the same ZIP skips all records as duplicates."""
    SessionLocal = async_sessionmaker(
        bind=real_pkg_engine, class_=AsyncSession, expire_on_commit=False
    )
    zip_bytes = _ZIP_PATH.read_bytes()

    async with SessionLocal() as session:
        first = await commit_package(
            file_bytes=zip_bytes,
            file_name=_ZIP_NAME,
            db=session,
            actor=real_pkg_actor,
            approval_batch_id=None,
            has_approve_permission=False,
        )

    async with SessionLocal() as session:
        second = await commit_package(
            file_bytes=zip_bytes,
            file_name=_ZIP_NAME,
            db=session,
            actor=real_pkg_actor,
            approval_batch_id=None,
            has_approve_permission=False,
        )

    assert second.created_items == 0
    assert second.created_versions == 0
    assert second.created_evidence_sources == 0
    assert second.created_region_rules == 0
    assert second.skipped_duplicates > 0


@pytest.mark.skipif(_ZIP_MISSING, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_real_package_db_duplicate_detection_in_preview(real_pkg_engine, real_pkg_actor):
    """After commit, preview detects existing records as DB duplicates."""
    SessionLocal = async_sessionmaker(
        bind=real_pkg_engine, class_=AsyncSession, expire_on_commit=False
    )
    zip_bytes = _ZIP_PATH.read_bytes()

    async with SessionLocal() as session:
        await commit_package(
            file_bytes=zip_bytes,
            file_name=_ZIP_NAME,
            db=session,
            actor=real_pkg_actor,
            approval_batch_id=None,
            has_approve_permission=False,
        )

    async with SessionLocal() as session:
        preview = await preview_package(zip_bytes, _ZIP_NAME, session)

    assert preview.duplicate_summary.existing_external_id_in_db == _EXPECTED["total_items"]
    assert preview.duplicate_summary.existing_hash_in_db == _EXPECTED["total_items"]
