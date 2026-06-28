#!/usr/bin/env python3
"""
Preview a content package (CSV or ZIP) against the import pipeline.

Usage:
    python scripts/preview_content_package.py <path/to/package.zip>

Runs preview_package() in an isolated in-memory SQLite database — no production
data is read or written. Exits 0 on clean preview, 1 if validation errors exist.

This script is safe to run against any content ZIP at any time. It never writes
to the production database and never auto-publishes anything.
"""
import asyncio
import json
import sys
from pathlib import Path

# Ensure backend package is importable when run from repo root
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.services.import_service import preview_package


async def _run_preview(package_path: Path) -> int:
    file_bytes = package_path.read_bytes()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        result = await preview_package(file_bytes, package_path.name, session)

    await engine.dispose()

    print(json.dumps(
        {
            "total_rows": result.total_rows,
            "valid_rows": result.valid_rows,
            "invalid_rows": result.invalid_rows,
            "warnings": result.warnings,
            "errors_by_file": result.errors_by_file,
            "detected_content_types": result.detected_content_types,
            "duplicate_summary": result.duplicate_summary.model_dump(),
            "approval_batch_required": result.approval_batch_required,
            "row_errors": [e.model_dump() for e in result.row_errors[:20]],
            "file_summaries": [s.model_dump() for s in result.file_summaries],
        },
        indent=2,
        ensure_ascii=False,
    ))

    if result.invalid_rows > 0 or result.errors_by_file:
        print(f"\nPREVIEW FAILED: {result.invalid_rows} invalid rows across "
              f"{len(result.errors_by_file)} files.", file=sys.stderr)
        return 1

    print(f"\nPREVIEW PASSED: {result.valid_rows} valid rows, 0 errors.", file=sys.stderr)
    return 0


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <package.csv|package.zip>", file=sys.stderr)
        sys.exit(2)

    package_path = Path(sys.argv[1])
    if not package_path.exists():
        print(f"File not found: {package_path}", file=sys.stderr)
        sys.exit(2)

    exit_code = asyncio.run(_run_preview(package_path))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
