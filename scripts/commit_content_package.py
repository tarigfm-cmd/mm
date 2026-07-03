#!/usr/bin/env python3
"""
Controlled local commit of a content package (CSV or ZIP).

Usage:
    python scripts/commit_content_package.py <path/to/package.zip>

Runs commit_package() in an isolated in-memory SQLite database — no production
data is read or written. The Docker daemon is not required; isolation comes from
the in-memory engine which is discarded on exit.

After the first commit the same ZIP is re-committed to verify idempotency
(second pass must create 0 items and skip all as duplicates).

Exits 0 on success, 1 on unexpected failure.

IMPORTANT: This script never writes to production. All DB operations use
sqlite+aiosqlite:///:memory: and are discarded when the process exits.
"""
import asyncio
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.database import Base
from app.models.governance import (
    ContentItem,
    ContentVersion,
    EvidenceSource,
    ImportBatch,
    RegionPublishingRule,
)
from app.models.identity import User
from app.services.import_service import commit_package


async def _run(package_path: Path) -> int:
    file_bytes = package_path.read_bytes()
    file_name = package_path.name

    # --- Isolated in-memory engine ---
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create an actor (not persisted to any real DB)
    async with SessionLocal() as s:
        actor = User(
            email="commit-script@local.dev",
            username="commit_actor",
            hashed_password=hash_password("LocalOnly1!"),
            full_name="Local Commit Script",
            is_active=True,
            is_superuser=True,
        )
        s.add(actor)
        await s.commit()
        await s.refresh(actor)

    # --- First commit ---
    print(f"[1/2] Committing {file_name} ...", flush=True)
    async with SessionLocal() as session:
        result1 = await commit_package(
            file_bytes=file_bytes,
            file_name=file_name,
            db=session,
            actor=actor,
            approval_batch_id=None,
            has_approve_permission=False,
        )

    print(json.dumps({
        "pass": "first",
        "created_items": result1.created_items,
        "created_versions": result1.created_versions,
        "created_evidence_sources": result1.created_evidence_sources,
        "created_region_rules": result1.created_region_rules,
        "skipped_duplicates": result1.skipped_duplicates,
        "invalid_rows": result1.invalid_rows,
        "import_batch_id": result1.import_batch_id,
    }, indent=2))

    # --- Verify DB counts by content_type ---
    async with SessionLocal() as session:
        type_rows = await session.execute(
            select(ContentItem.content_type, func.count(ContentItem.id))
            .group_by(ContentItem.content_type)
        )
        by_type = {row[0]: row[1] for row in type_rows.all()}

        total_items = (await session.execute(select(func.count(ContentItem.id)))).scalar()
        total_versions = (await session.execute(select(func.count(ContentVersion.id)))).scalar()
        total_evidence = (await session.execute(select(func.count(EvidenceSource.id)))).scalar()
        total_rules = (await session.execute(select(func.count(RegionPublishingRule.id)))).scalar()
        total_batches = (await session.execute(select(func.count(ImportBatch.id)))).scalar()

        published = (
            await session.execute(
                select(func.count(ContentItem.id)).where(ContentItem.status == "published")
            )
        ).scalar()
        pending = (
            await session.execute(
                select(func.count(ContentItem.id)).where(ContentItem.status == "pending_review")
            )
        ).scalar()
        active_rules = (
            await session.execute(
                select(func.count(RegionPublishingRule.id))
                .where(RegionPublishingRule.is_active.is_(True))
            )
        ).scalar()

    print("\n--- DB state after first commit ---")
    print(json.dumps({
        "content_items_by_type": by_type,
        "total_content_items": total_items,
        "total_content_versions": total_versions,
        "total_evidence_sources": total_evidence,
        "total_region_rules": total_rules,
        "total_import_batches": total_batches,
        "items_published": published,
        "items_pending_review": pending,
        "region_rules_active": active_rules,
    }, indent=2))

    if published != 0:
        print("\nFAIL: imported items must not be published", file=sys.stderr)
        return 1
    if active_rules != 0:
        print("\nFAIL: imported region rules must be inactive", file=sys.stderr)
        return 1

    # --- Second commit (idempotency check) ---
    print("\n[2/2] Re-committing same ZIP (idempotency check) ...", flush=True)
    async with SessionLocal() as session:
        result2 = await commit_package(
            file_bytes=file_bytes,
            file_name=file_name,
            db=session,
            actor=actor,
            approval_batch_id=None,
            has_approve_permission=False,
        )

    print(json.dumps({
        "pass": "second (idempotency)",
        "created_items": result2.created_items,
        "created_versions": result2.created_versions,
        "created_evidence_sources": result2.created_evidence_sources,
        "created_region_rules": result2.created_region_rules,
        "skipped_duplicates": result2.skipped_duplicates,
        "invalid_rows": result2.invalid_rows,
    }, indent=2))

    # DB totals must not have grown
    async with SessionLocal() as session:
        items_after2 = (await session.execute(select(func.count(ContentItem.id)))).scalar()
        batches_after2 = (await session.execute(select(func.count(ImportBatch.id)))).scalar()

    print(f"\nItems after re-import: {items_after2} (expected {total_items} — unchanged)")
    print(f"ImportBatch records: {batches_after2} (two batches created, both committed)")

    if result2.created_items != 0:
        print("\nFAIL: second import should create 0 new items", file=sys.stderr)
        return 1
    if items_after2 != total_items:
        print(f"\nFAIL: item count grew from {total_items} to {items_after2}", file=sys.stderr)
        return 1

    print("\nCOMMIT VERIFIED: all checks passed.", file=sys.stderr)
    return 0


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <package.zip>", file=sys.stderr)
        sys.exit(2)
    package_path = Path(sys.argv[1])
    if not package_path.exists():
        print(f"File not found: {package_path}", file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(_run(package_path)))


if __name__ == "__main__":
    main()
