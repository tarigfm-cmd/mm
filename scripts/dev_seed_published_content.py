#!/usr/bin/env python3
"""
DEV/DEMO SEED SCRIPT — NOT FOR PRODUCTION USE.

Creates the minimum database records needed to exercise the full learner journey
in a fresh development environment:

  1. One superuser admin account (dev-admin@pharmlearn.dev / DevAdmin1!)
  2. One ContentItem (content_type=drill, non-clinical structural example)
  3. One ContentVersion with a minimal payload
  4. One approved ClinicalReview
  5. One PublicationRecord for region=UK

The item created is a structural demonstration drill (dose-unit conversion
framework question). It contains NO invented clinical advice — only arithmetic
scaffolding that does not constitute medical guidance.

Safety guarantees:
  - Idempotent: if published content already exists, the script exits cleanly.
  - Never auto-publishes real imported content without explicit confirmation.
  - Never runs in production (checks DB URL is not a production host).
  - Never invents clinical scenarios.
  - Completely safe to delete: drop the content item to remove all seed data.

Usage:
    cd /path/to/repo
    python scripts/dev_seed_published_content.py

    # Or with a custom DB URL:
    DATABASE_URL=postgresql+asyncpg://... python scripts/dev_seed_published_content.py
"""
import asyncio
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Make backend importable from repo root
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.database import Base
from app.models.governance import (
    ClinicalReview,
    ContentItem,
    ContentVersion,
    PublicationRecord,
)
from app.models.identity import User

# ---------------------------------------------------------------------------
# Seed constants (dev-only credentials — never use in production)
# ---------------------------------------------------------------------------

ADMIN_EMAIL = "dev-admin@pharmlearn.dev"
ADMIN_USERNAME = "devadmin"
ADMIN_PASSWORD = "DevAdmin1!"
ADMIN_FULL_NAME = "Dev Admin"

SEED_ITEM_EXTERNAL_ID = "SEED-DEMO-DRILL-001"
SEED_ITEM_TITLE = "Dose Unit Conversion: mg to mcg (Framework Demo)"
SEED_ITEM_DOMAIN = "Pharmaceutical Calculations"
SEED_ITEM_REGION = "UK"

SEED_PAYLOAD = {
    "prompt": (
        "A prescription reads: amoxicillin 500 mg three times daily. "
        "Convert this to micrograms per dose."
    ),
    "context": "Unit conversion — foundational pharmacy mathematics.",
    "domain": "Pharmaceutical Calculations",
    "subtopic": "Unit conversion",
    "difficulty": "1",
    # Hidden from learners before submission (revealed after):
    "correct_answer_or_expected_response": "500,000 mcg",
    "scoring_rubric": "Accept '500000 mcg', '500,000 mcg', or '500000'. Unit must be present.",
}

SEED_CHANGE_SUMMARY = "Initial dev seed — demonstration drill item."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _content_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _check_not_production(db_url: str) -> None:
    """Refuse to run against obvious production hosts."""
    danger_signals = [
        "rds.amazonaws.com",
        "supabase.co",
        "neon.tech",
        "railway.app",
        "render.com",
        "fly.io",
        "heroku",
    ]
    lower = db_url.lower()
    for signal in danger_signals:
        if signal in lower:
            print(
                f"\nERROR: database URL looks like a production host ({signal}).\n"
                "This seed script must only run in development.\n",
                file=sys.stderr,
            )
            sys.exit(1)


# ---------------------------------------------------------------------------
# Main seed logic
# ---------------------------------------------------------------------------

async def seed(db_url: str) -> None:
    _check_not_production(db_url)

    engine = create_async_engine(db_url, echo=False)

    # Ensure tables exist (idempotent in dev)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        # ── 1. Check for existing published content ─────────────────────────
        existing = (await db.execute(
            select(PublicationRecord)
            .where(PublicationRecord.publication_status == "published")
            .limit(1)
        )).scalar_one_or_none()

        if existing:
            item = (await db.execute(
                select(ContentItem).where(ContentItem.id == existing.content_item_id)
            )).scalar_one_or_none()
            title = item.title if item else "(unknown)"
            print(f"\nPublished content already exists: '{title}'")
            print("Skipping seed — database is already primed for the learner journey.")
            print(f"\nLog in at http://localhost:5173/login")
            print(f"Admin account: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
            print("Browse training: http://localhost:5173/learn/content\n")
            return

        # ── 2. Create or find admin user ────────────────────────────────────
        admin = (await db.execute(
            select(User).where(User.email == ADMIN_EMAIL)
        )).scalar_one_or_none()

        if admin is None:
            admin = User(
                id=uuid.uuid4(),
                email=ADMIN_EMAIL,
                username=ADMIN_USERNAME,
                hashed_password=hash_password(ADMIN_PASSWORD),
                full_name=ADMIN_FULL_NAME,
                is_active=True,
                is_verified=True,
                is_superuser=True,
            )
            db.add(admin)
            await db.flush()
            print(f"Created admin user: {ADMIN_EMAIL}")
        else:
            print(f"Using existing admin user: {ADMIN_EMAIL}")

        # ── 3. Create ContentItem ────────────────────────────────────────────
        item = (await db.execute(
            select(ContentItem).where(ContentItem.external_id == SEED_ITEM_EXTERNAL_ID)
        )).scalar_one_or_none()

        if item is None:
            item = ContentItem(
                id=uuid.uuid4(),
                external_id=SEED_ITEM_EXTERNAL_ID,
                title=SEED_ITEM_TITLE,
                content_type="drill",
                domain=SEED_ITEM_DOMAIN,
                difficulty="1",
                region_scope=[SEED_ITEM_REGION],
                status="clinically_approved",
                created_by=admin.id,
            )
            db.add(item)
            await db.flush()
            print(f"Created ContentItem: '{SEED_ITEM_TITLE}'")
        else:
            print(f"Using existing ContentItem: '{item.title}'")

        # ── 4. Create ContentVersion ─────────────────────────────────────────
        version = (await db.execute(
            select(ContentVersion)
            .where(ContentVersion.content_item_id == item.id)
            .order_by(ContentVersion.version_number.desc())
            .limit(1)
        )).scalar_one_or_none()

        if version is None:
            version = ContentVersion(
                id=uuid.uuid4(),
                content_item_id=item.id,
                version_number=1,
                payload_json=SEED_PAYLOAD,
                content_hash=_content_hash(SEED_PAYLOAD),
                change_summary=SEED_CHANGE_SUMMARY,
                created_by=admin.id,
                is_current=True,
            )
            db.add(version)
            await db.flush()
            # Update current_version_id back-reference
            item.current_version_id = version.id
            print("Created ContentVersion v1")
        else:
            print(f"Using existing ContentVersion v{version.version_number}")

        # ── 5. Create ClinicalReview (approved) ──────────────────────────────
        review = (await db.execute(
            select(ClinicalReview)
            .where(
                ClinicalReview.content_item_id == item.id,
                ClinicalReview.content_version_id == version.id,
                ClinicalReview.review_decision == "approved",
            )
            .limit(1)
        )).scalar_one_or_none()

        if review is None:
            review = ClinicalReview(
                id=uuid.uuid4(),
                content_item_id=item.id,
                content_version_id=version.id,
                reviewer_user_id=admin.id,
                reviewer_role="pharmacist",
                reviewer_team_name="Dev Seed",
                review_decision="approved",
                comments="Automatically approved by dev seed script.",
                signed_off_at=datetime.now(timezone.utc),
            )
            db.add(review)
            await db.flush()
            print("Created ClinicalReview (approved)")
        else:
            print("ClinicalReview (approved) already exists")

        # ── 6. Publish for UK ────────────────────────────────────────────────
        publication = (await db.execute(
            select(PublicationRecord)
            .where(
                PublicationRecord.content_item_id == item.id,
                PublicationRecord.region_code == SEED_ITEM_REGION,
                PublicationRecord.publication_status == "published",
            )
            .limit(1)
        )).scalar_one_or_none()

        if publication is None:
            publication = PublicationRecord(
                id=uuid.uuid4(),
                content_item_id=item.id,
                content_version_id=version.id,
                region_code=SEED_ITEM_REGION,
                published_by=admin.id,
                published_at=datetime.now(timezone.utc),
                publication_status="published",
                reason="Dev seed",
            )
            db.add(publication)
            # Also mark the item as published
            item.status = "published"
            print(f"Published to region: {SEED_ITEM_REGION}")
        else:
            print(f"Already published for region: {SEED_ITEM_REGION}")

        await db.commit()

    await engine.dispose()

    print("\nSeed complete!")
    print(f"\n  Admin login:    {ADMIN_EMAIL}")
    print(f"  Password:       {ADMIN_PASSWORD}")
    print(f"  Content item:   {SEED_ITEM_TITLE}")
    print(f"  External ID:    {SEED_ITEM_EXTERNAL_ID}")
    print(f"  Region:         {SEED_ITEM_REGION}")
    print("\n  Start the app:  docker-compose up")
    print("  Browse:         http://localhost:5173/learn/content")
    print("  Admin UI:       http://localhost:5173/admin/governance\n")


def _get_db_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return url

    # Try to read from .env in repo root
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")

    # Docker Compose default
    return "postgresql+asyncpg://postgres:postgres@localhost:5432/pharmlearn"


def main() -> None:
    db_url = _get_db_url()
    print(f"Connecting to: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    try:
        asyncio.run(seed(db_url))
    except Exception as exc:
        print(f"\nSeed failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
