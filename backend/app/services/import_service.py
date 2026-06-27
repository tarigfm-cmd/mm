"""Bulk CSV/ZIP import pipeline for community pharmacy governance content."""
import csv
import hashlib
import io
import json
import os
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import (
    ContentItem,
    ContentVersion,
    EvidenceSource,
    ImportBatch,
    ImportRowError,
    RegionPublishingRule,
)
from app.models.identity import User
from app.schemas.import_schema import (
    CommitResult,
    DuplicateSummary,
    FileSummary,
    PreviewResult,
    RowError,
)
from app.services.audit import log_action

# ---------------------------------------------------------------------------
# Security limits
# ---------------------------------------------------------------------------
MAX_UPLOAD_BYTES = 200 * 1024 * 1024        # 200 MB
MAX_UNCOMPRESSED_BYTES = 600 * 1024 * 1024  # 600 MB total uncompressed
MAX_ZIP_FILES = 20
MAX_ROWS_PER_FILE = 10_000

# ---------------------------------------------------------------------------
# Allowed ZIP entry names
# ---------------------------------------------------------------------------
_ALLOWED_ZIP_NAMES = frozenset({
    "case_bank_7500.csv",
    "simulation_blueprints_1200.csv",
    "osce_stations_400.csv",
    "prescription_screening_1200.csv",
    "drills_1200.csv",
    "evidence_library.csv",
    "localization_rules.csv",
    "games_rewards.csv",
    "taxonomy.csv",
    "audit_checklist.csv",
    "csv_import_schema.csv",
    "manifest.json",
})

# Reference-only: parsed but never imported as ContentItem/ContentVersion
_REFERENCE_ONLY = frozenset({
    "games_rewards.csv",
    "taxonomy.csv",
    "audit_checklist.csv",
    "csv_import_schema.csv",
    "manifest.json",
})

# ---------------------------------------------------------------------------
# Learner-content CSV specifications
# ---------------------------------------------------------------------------
_LEARNER_SPECS: dict[str, dict] = {
    "case_bank_7500.csv": {
        "content_type": "case",
        "id_col": "case_id",
        "required_cols": {
            "case_id", "domain", "subtopic", "region_localization",
            "difficulty_1_5", "evidence_ids", "review_status",
            "red_flags_to_screen", "expected_decision",
        },
    },
    "simulation_blueprints_1200.csv": {
        "content_type": "simulation",
        "id_col": "simulation_id",
        "required_cols": {
            "simulation_id", "domain", "subtopic", "region_localization",
            "difficulty_1_5", "evidence_ids", "review_status",
            "hidden_risk", "failure_mode",
        },
    },
    "osce_stations_400.csv": {
        "content_type": "osce_station",
        "id_col": "osce_id",
        "required_cols": {
            "osce_id", "station_title", "domain", "region_localization",
            "difficulty_1_5", "evidence_ids", "review_status",
            "candidate_task", "critical_fail", "scoring_rubric",
        },
    },
    "prescription_screening_1200.csv": {
        "content_type": "prescription_screening",
        "id_col": "screening_id",
        "required_cols": {
            "screening_id", "region_localization", "difficulty_1_5",
            "evidence_ids", "review_status",
            "safety_concern", "expected_pharmacist_action",
        },
    },
    "drills_1200.csv": {
        "content_type": "drill",
        "id_col": "drill_id",
        "required_cols": {
            "drill_id", "region_localization", "difficulty_1_5",
            "evidence_ids", "review_status",
            "prompt", "correct_answer_or_expected_response",
        },
    },
}

_EVIDENCE_REQUIRED_COLS = {"evidence_id", "source_name", "source_type", "url"}
_LOCALIZATION_REQUIRED_COLS = {"region", "regulatory_anchor"}

_VALID_LEARNER_REGIONS = frozenset({"UK", "US", "GCC", "AU"})
_VALID_DIFFICULTIES = frozenset({"1", "2", "3", "4", "5"})

# review_status values that map to clinically_approved
_APPROVED_REVIEW_STATUSES = frozenset({
    "team-approved", "clinically_approved", "approved",
    "pharmacist_approved", "human_approved", "reviewer_approved",
})

# ---------------------------------------------------------------------------
# Region normalization
# ---------------------------------------------------------------------------
_REGION_NORM: dict[str, str] = {
    "uk": "UK", "us": "US", "gcc": "GCC",
    "australia": "AU", "au": "AU",
    "global": "GLOBAL",
}


def _normalize_learner_region(raw: str) -> str | None:
    """Normalize a learner-content region string; return None if unrecognized."""
    norm = _REGION_NORM.get(raw.strip().lower())
    return norm if norm in _VALID_LEARNER_REGIONS else None


def _normalize_evidence_region(raw: str) -> str | None:
    """Normalize an evidence source region; GLOBAL is accepted here."""
    return _REGION_NORM.get(raw.strip().lower())


# ---------------------------------------------------------------------------
# Title synthesis (from row metadata — no clinical content changes)
# ---------------------------------------------------------------------------
def _derive_title(file_name: str, row: dict[str, str]) -> str:
    station = row.get("station_title", "").strip()
    if station:
        return station[:500]
    domain = row.get("domain", "").strip()
    subtopic = row.get("subtopic", "").strip()
    if domain and subtopic:
        return f"{domain} — {subtopic}"[:500]
    if domain:
        return domain[:500]
    if "prescription_screening" in file_name:
        issue = row.get("issue_type", "").strip()
        ext_id = row.get("screening_id", "").strip()
        label = issue or ext_id or "unknown"
        return f"Rx Screening — {label}"[:500]
    prompt = row.get("prompt", "").strip()
    if prompt:
        return prompt[:120]
    ext_id = (
        row.get("drill_id") or row.get("case_id") or row.get("simulation_id")
        or row.get("osce_id") or row.get("screening_id") or "Untitled"
    ).strip()
    return ext_id[:500]


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------
def _content_hash(external_id: str, content_type: str, row: dict[str, str]) -> str:
    canonical = json.dumps(
        {"__ext_id": external_id, "__ctype": content_type, **row},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Evidence IDs parsing
# ---------------------------------------------------------------------------
def _parse_evidence_ids(raw: str) -> list[str]:
    return [e.strip() for e in raw.split(";") if e.strip()] if raw.strip() else []


# ---------------------------------------------------------------------------
# CSV parsing helpers
# ---------------------------------------------------------------------------
def _parse_csv_bytes(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _csv_headers(content: bytes) -> set[str]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return set(reader.fieldnames or [])


# ---------------------------------------------------------------------------
# Security: parse and validate uploaded bytes
# ---------------------------------------------------------------------------
def _check_file_size(file_bytes: bytes, filename: str) -> None:
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"File size {len(file_bytes) // (1024*1024)} MB exceeds "
            f"maximum allowed {MAX_UPLOAD_BYTES // (1024*1024)} MB"
        )


def _check_extension(filename: str) -> str:
    """Return '.csv' or '.zip' or raise ValueError."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".csv", ".zip"):
        raise ValueError(
            f"Unsupported file type {ext!r}. Only .csv and .zip are accepted."
        )
    return ext


def _extract_zip(file_bytes: bytes) -> dict[str, bytes]:
    """
    Security-validated ZIP extraction.

    Returns {filename: content_bytes} for all valid entries.
    Raises ValueError on any security violation.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(file_bytes))
    except zipfile.BadZipFile:
        raise ValueError("Uploaded file is not a valid ZIP archive")

    infos = zf.infolist()
    if len(infos) > MAX_ZIP_FILES:
        raise ValueError(
            f"ZIP contains {len(infos)} entries; maximum allowed is {MAX_ZIP_FILES}"
        )

    total_uncompressed = 0
    result: dict[str, bytes] = {}

    for info in infos:
        name = info.filename

        # Reject absolute paths
        if os.path.isabs(name) or name.startswith("/"):
            raise ValueError("ZIP entry has absolute path: rejected")

        # Reject path traversal
        parts = name.replace("\\", "/").split("/")
        if ".." in parts:
            raise ValueError("ZIP entry contains path traversal sequence: rejected")

        # Reject nested directories (only top-level files allowed)
        clean_parts = [p for p in parts if p]
        if len(clean_parts) > 1:
            raise ValueError(
                f"ZIP entries must be at the top level, not in subdirectories: rejected"
            )

        # Reject nested ZIPs
        if name.lower().endswith(".zip"):
            raise ValueError("Nested ZIP files are not allowed")

        base_name = os.path.basename(name)

        # Reject unsupported file names
        if base_name not in _ALLOWED_ZIP_NAMES:
            raise ValueError(
                f"Unrecognized file in ZIP: {base_name!r}. "
                "Only files from the recognized content bank package are accepted."
            )

        total_uncompressed += info.file_size
        if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
            raise ValueError(
                f"ZIP total uncompressed size exceeds "
                f"{MAX_UNCOMPRESSED_BYTES // (1024 * 1024)} MB limit"
            )

        result[base_name] = zf.read(info.filename)

    zf.close()
    return result


# ---------------------------------------------------------------------------
# Internal row validation types
# ---------------------------------------------------------------------------
@dataclass
class _RowResult:
    row_number: int
    external_id: str | None
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    content_hash: str | None = None
    normalized_regions: list[str] = field(default_factory=list)
    is_approved: bool = False
    parsed_row: dict = field(default_factory=dict)


@dataclass
class _FileResult:
    file_name: str
    content_type: str | None
    is_reference: bool
    total_rows: int = 0
    valid: list[_RowResult] = field(default_factory=list)
    invalid: list[_RowResult] = field(default_factory=list)
    dup_in_upload: list[_RowResult] = field(default_factory=list)
    missing_cols: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Row validation
# ---------------------------------------------------------------------------
def _validate_learner_row(
    row: dict[str, str],
    row_num: int,
    spec: dict,
    seen_ext_ids: set[str],
    seen_hashes: set[str],
) -> _RowResult:
    errors: list[str] = []
    warnings: list[str] = []

    id_col = spec["id_col"]
    external_id = row.get(id_col, "").strip() or None

    if not external_id:
        errors.append(f"Missing required field: {id_col!r} (external_id)")
        return _RowResult(row_num, None, False, errors, warnings)

    # Required columns already checked at header level; check blank values here
    for col in spec["required_cols"] - {id_col}:
        if not row.get(col, "").strip():
            errors.append(f"Required field {col!r} is blank")

    # Region validation
    raw_region = row.get("region_localization", "").strip()
    norm_region = _normalize_learner_region(raw_region)
    normalized_regions: list[str] = []
    if not raw_region:
        errors.append("Missing required field: 'region_localization'")
    elif norm_region is None:
        errors.append(
            f"Invalid region_localization {raw_region!r}. "
            f"Accepted values: UK, US, GCC, Australia (AU)"
        )
    else:
        normalized_regions = [norm_region]

    # Difficulty validation
    diff_raw = row.get("difficulty_1_5", "").strip()
    if diff_raw and diff_raw not in _VALID_DIFFICULTIES:
        errors.append(f"Invalid difficulty_1_5 {diff_raw!r}; expected 1–5")

    # Evidence IDs format (semicolon-separated, non-empty)
    ev_raw = row.get("evidence_ids", "").strip()
    if not ev_raw:
        warnings.append("evidence_ids is blank; item will have no evidence linkage")
    else:
        ev_ids = _parse_evidence_ids(ev_raw)
        if not ev_ids:
            warnings.append("evidence_ids could not be parsed")

    valid = not errors

    # Hash only for valid rows
    c_hash: str | None = None
    is_dup_upload = False

    if valid:
        c_hash = _content_hash(external_id, spec["content_type"], dict(row))

        # Duplicate detection (within upload)
        if external_id in seen_ext_ids or c_hash in seen_hashes:
            is_dup_upload = True
        else:
            seen_ext_ids.add(external_id)
            seen_hashes.add(c_hash)

    is_approved = _APPROVED_REVIEW_STATUSES.issuperset(
        {row.get("review_status", "").strip().lower()}
    ) and bool(row.get("review_status", "").strip())

    rr = _RowResult(
        row_number=row_num,
        external_id=external_id,
        valid=valid and not is_dup_upload,
        errors=errors,
        warnings=warnings,
        content_hash=c_hash,
        normalized_regions=normalized_regions,
        is_approved=is_approved,
        parsed_row=dict(row),
    )
    if is_dup_upload:
        rr.errors.append(f"Duplicate external_id or content_hash within this upload")
    return rr


def _validate_evidence_row(row: dict[str, str], row_num: int) -> _RowResult:
    errors: list[str] = []
    ext_id = row.get("evidence_id", "").strip() or None
    for col in ("source_name", "source_type", "url"):
        if not row.get(col, "").strip():
            errors.append(f"Required field {col!r} is blank")
    if not ext_id:
        errors.append("Required field 'evidence_id' is blank")
    url = row.get("url", "").strip()
    if url and not (url.startswith("http://") or url.startswith("https://")):
        errors.append(f"Field 'url' does not look like a valid URL")
    return _RowResult(row_num, ext_id, not errors, errors)


def _validate_localization_row(row: dict[str, str], row_num: int) -> _RowResult:
    errors: list[str] = []
    raw_region = row.get("region", "").strip()
    if not raw_region:
        errors.append("Required field 'region' is blank")
        return _RowResult(row_num, None, False, errors)
    norm = _REGION_NORM.get(raw_region.lower())
    if norm is None:
        errors.append(
            f"Unrecognized region {raw_region!r}. "
            f"Expected: UK, US, GCC, Australia"
        )
        return _RowResult(row_num, raw_region, False, errors)
    if not row.get("regulatory_anchor", "").strip():
        errors.append("Required field 'regulatory_anchor' is blank")
    return _RowResult(row_num, raw_region, not errors, errors)


# ---------------------------------------------------------------------------
# Parse + validate a single recognized file's bytes
# ---------------------------------------------------------------------------
def _process_file(file_name: str, content: bytes) -> _FileResult:
    is_ref = file_name in _REFERENCE_ONLY
    spec = _LEARNER_SPECS.get(file_name)
    is_evidence = file_name == "evidence_library.csv"
    is_localization = file_name == "localization_rules.csv"
    content_type = spec["content_type"] if spec else None

    result = _FileResult(
        file_name=file_name,
        content_type=content_type,
        is_reference=is_ref,
    )

    if is_ref:
        # Just count rows for reporting
        rows = _parse_csv_bytes(content)
        result.total_rows = len(rows)
        return result

    rows = _parse_csv_bytes(content)
    result.total_rows = len(rows)

    if len(rows) > MAX_ROWS_PER_FILE:
        result.invalid = [
            _RowResult(
                1, None, False,
                [f"File exceeds maximum row count of {MAX_ROWS_PER_FILE}; "
                 f"found {len(rows)} rows"],
            )
        ]
        return result

    if spec:
        headers = _csv_headers(content)
        missing = sorted(spec["required_cols"] - headers)
        if missing:
            result.missing_cols = missing
            return result

        seen_ext_ids: set[str] = set()
        seen_hashes: set[str] = set()
        for i, row in enumerate(rows, start=2):  # row 1 = header
            rr = _validate_learner_row(row, i, spec, seen_ext_ids, seen_hashes)
            if "Duplicate" in " ".join(rr.errors):
                result.dup_in_upload.append(rr)
            elif rr.valid:
                result.valid.append(rr)
            else:
                result.invalid.append(rr)

    elif is_evidence:
        headers = _csv_headers(content)
        missing = sorted(_EVIDENCE_REQUIRED_COLS - headers)
        if missing:
            result.missing_cols = missing
            return result
        for i, row in enumerate(rows, start=2):
            rr = _validate_evidence_row(row, i)
            (result.valid if rr.valid else result.invalid).append(rr)

    elif is_localization:
        headers = _csv_headers(content)
        missing = sorted(_LOCALIZATION_REQUIRED_COLS - headers)
        if missing:
            result.missing_cols = missing
            return result
        for i, row in enumerate(rows, start=2):
            rr = _validate_localization_row(row, i)
            (result.valid if rr.valid else result.invalid).append(rr)

    return result


# ---------------------------------------------------------------------------
# DB duplicate detection
# ---------------------------------------------------------------------------
async def _db_duplicate_external_ids(
    db: AsyncSession, ext_ids: list[str]
) -> set[str]:
    if not ext_ids:
        return set()
    result = await db.execute(
        select(ContentItem.external_id).where(ContentItem.external_id.in_(ext_ids))
    )
    return set(result.scalars().all())


async def _db_duplicate_hashes(
    db: AsyncSession, hashes: list[str]
) -> set[str]:
    if not hashes:
        return set()
    result = await db.execute(
        select(ContentVersion.content_hash).where(
            ContentVersion.content_hash.in_(hashes)
        )
    )
    return set(result.scalars().all())


async def _db_duplicate_evidence_urls(
    db: AsyncSession, urls: list[str]
) -> set[str]:
    if not urls:
        return set()
    result = await db.execute(
        select(EvidenceSource.url).where(EvidenceSource.url.in_(urls))
    )
    return set(result.scalars().all())


async def _db_duplicate_region_rules(
    db: AsyncSession, region_codes: list[str]
) -> set[str]:
    """Return region_codes that already have an active=False rule (for skipping)."""
    if not region_codes:
        return set()
    result = await db.execute(
        select(RegionPublishingRule.region_code).where(
            RegionPublishingRule.region_code.in_(region_codes),
            RegionPublishingRule.is_active.is_(False),
            RegionPublishingRule.content_type.is_(None),
        )
    )
    return set(result.scalars().all())


# ---------------------------------------------------------------------------
# Package entry point: parse files bytes dict → list[_FileResult]
# ---------------------------------------------------------------------------
def _parse_package(files: dict[str, bytes]) -> list[_FileResult]:
    results: list[_FileResult] = []
    for name, content in files.items():
        if name == "manifest.json":
            results.append(_FileResult(name, None, True, 0))
            continue
        results.append(_process_file(name, content))
    return results


# ---------------------------------------------------------------------------
# Public API: preview_package
# ---------------------------------------------------------------------------
async def preview_package(
    file_bytes: bytes,
    file_name: str,
    db: AsyncSession,
) -> PreviewResult:
    _check_file_size(file_bytes, file_name)
    ext = _check_extension(file_name)

    if ext == ".zip":
        files = _extract_zip(file_bytes)
    else:
        safe_name = os.path.basename(file_name)
        files = {safe_name: file_bytes}

    file_results = _parse_package(files)

    # Aggregate counts
    total = valid = invalid = 0
    file_summaries: list[FileSummary] = []
    all_errors_by_file: dict[str, list[str]] = {}
    all_warnings: list[str] = []
    detected_types: set[str] = set()
    dup_in_upload_ext_ids = dup_in_upload_hashes = 0
    approval_batch_required = False

    all_valid_rows: list[_RowResult] = []

    for fr in file_results:
        file_errors: list[str] = []

        if fr.missing_cols:
            file_errors.append(
                f"Missing required columns: {', '.join(fr.missing_cols)}"
            )
            all_errors_by_file[fr.file_name] = file_errors
            file_summaries.append(FileSummary(
                file_name=fr.file_name,
                content_type=fr.content_type,
                total_rows=fr.total_rows,
                valid_rows=0,
                invalid_rows=fr.total_rows,
                skipped_duplicates=0,
                is_reference_only=fr.is_reference,
            ))
            invalid += fr.total_rows
            total += fr.total_rows
            continue

        valid_count = len(fr.valid)
        invalid_count = len(fr.invalid)
        dup_count = len(fr.dup_in_upload)

        total += fr.total_rows
        valid += valid_count
        invalid += invalid_count
        dup_in_upload_ext_ids += dup_count

        if fr.content_type:
            detected_types.add(fr.content_type)

        for rr in fr.invalid:
            for e in rr.errors:
                file_errors.append(f"Row {rr.row_number}: {e}")
        for rr in fr.dup_in_upload:
            file_errors.append(f"Row {rr.row_number}: duplicate within upload")

        for rr in fr.valid:
            all_warnings.extend(rr.warnings)
            if rr.is_approved:
                approval_batch_required = True
        all_valid_rows.extend(fr.valid)

        if file_errors:
            all_errors_by_file[fr.file_name] = file_errors

        file_summaries.append(FileSummary(
            file_name=fr.file_name,
            content_type=fr.content_type,
            total_rows=fr.total_rows,
            valid_rows=valid_count,
            invalid_rows=invalid_count,
            skipped_duplicates=dup_count,
            is_reference_only=fr.is_reference,
        ))

    # DB duplicate checks
    learner_valid = [r for r in all_valid_rows if r.content_hash]
    ext_ids = [r.external_id for r in learner_valid if r.external_id]
    hashes = [r.content_hash for r in learner_valid if r.content_hash]

    existing_ext_ids = await _db_duplicate_external_ids(db, ext_ids)
    existing_hashes = await _db_duplicate_hashes(db, hashes)

    # Build row errors list (limit to first 100 to avoid huge responses)
    row_errors_out: list = []
    for fr in file_results:
        for rr in (fr.invalid + fr.dup_in_upload)[:100]:
            for e in rr.errors:
                row_errors_out.append(RowError(
                    file_name=fr.file_name,
                    row_number=rr.row_number,
                    external_id=rr.external_id,
                    error_code="validation_error",
                    message=e,
                ))

    return PreviewResult(
        total_rows=total,
        valid_rows=valid,
        invalid_rows=invalid,
        warnings=list(dict.fromkeys(all_warnings)),  # deduplicate
        errors_by_file=all_errors_by_file,
        file_summaries=file_summaries,
        detected_content_types=sorted(detected_types),
        duplicate_summary=DuplicateSummary(
            duplicate_external_id_in_upload=dup_in_upload_ext_ids,
            duplicate_hash_in_upload=0,  # tracked via same set
            existing_external_id_in_db=len(existing_ext_ids),
            existing_hash_in_db=len(existing_hashes),
        ),
        approval_batch_required=approval_batch_required,
        row_errors=row_errors_out[:100],
    )


# ---------------------------------------------------------------------------
# Public API: commit_package
# ---------------------------------------------------------------------------
async def commit_package(
    file_bytes: bytes,
    file_name: str,
    db: AsyncSession,
    actor: User,
    approval_batch_id: uuid.UUID | None = None,
    has_approve_permission: bool = False,
) -> CommitResult:
    _check_file_size(file_bytes, file_name)
    ext = _check_extension(file_name)

    if ext == ".zip":
        files = _extract_zip(file_bytes)
    else:
        safe_name = os.path.basename(file_name)
        files = {safe_name: file_bytes}

    file_results = _parse_package(files)

    # Collect all valid learner rows for DB duplicate check
    all_valid_learner: list[tuple[str, _RowResult]] = []  # (file_name, row_result)
    all_valid_evidence: list[tuple[str, dict]] = []
    all_valid_localization: list[tuple[str, dict]] = []

    for fr in file_results:
        if fr.content_type:
            for rr in fr.valid:
                all_valid_learner.append((fr.file_name, rr))
        elif fr.file_name == "evidence_library.csv":
            raw_rows = _parse_csv_bytes(files[fr.file_name])
            for rr in fr.valid:
                all_valid_evidence.append((fr.file_name, raw_rows[rr.row_number - 2]))
        elif fr.file_name == "localization_rules.csv":
            raw_rows = _parse_csv_bytes(files[fr.file_name])
            for rr in fr.valid:
                all_valid_localization.append((fr.file_name, raw_rows[rr.row_number - 2]))

    # DB duplicate checks for learner content
    ext_ids = [rr.external_id for _, rr in all_valid_learner if rr.external_id]
    hashes = [rr.content_hash for _, rr in all_valid_learner if rr.content_hash]
    existing_ext_ids = await _db_duplicate_external_ids(db, ext_ids)
    existing_hashes = await _db_duplicate_hashes(db, hashes)

    # Check if any rows would be clinically_approved
    any_approved = any(
        rr.is_approved and approval_batch_id is not None
        for _, rr in all_valid_learner
        if rr.external_id not in existing_ext_ids
    )
    if any_approved and not has_approve_permission:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="Permission 'content.approve' is required to import clinically_approved rows. "
                   "Provide an approval_batch_id only with the required permission.",
        )

    # Create ImportBatch record
    import_batch = ImportBatch(
        source_file_name=os.path.basename(file_name),
        package_type="zip" if ext == ".zip" else "csv",
        status="committed",
        uploaded_by_user_id=actor.id,
        approval_batch_id=approval_batch_id,
        committed_at=datetime.now(timezone.utc),
    )
    db.add(import_batch)
    await db.flush()  # get import_batch.id

    created_items = 0
    created_versions = 0
    skipped = 0
    invalid_count = sum(len(fr.invalid) + len(fr.dup_in_upload) for fr in file_results)
    warnings: list[str] = []
    row_errors_out: list[RowError] = []

    # --- Commit learner content ---
    for fname, rr in all_valid_learner:
        if rr.external_id in existing_ext_ids or rr.content_hash in existing_hashes:
            skipped += 1
            continue

        spec = _LEARNER_SPECS[fname]
        row = rr.parsed_row

        determine_status = (
            "clinically_approved"
            if (rr.is_approved and approval_batch_id is not None and has_approve_permission)
            else "pending_review"
        )

        item_id = uuid.uuid4()
        version_id = uuid.uuid4()

        item = ContentItem(
            id=item_id,
            external_id=rr.external_id,
            title=_derive_title(fname, row),
            content_type=spec["content_type"],
            domain=row.get("domain", "").strip() or None,
            difficulty=row.get("difficulty_1_5", "").strip() or None,
            region_scope=rr.normalized_regions,
            status=determine_status,
            current_version_id=version_id,
            created_by=actor.id,
        )

        ev_ids = _parse_evidence_ids(row.get("evidence_ids", ""))
        version = ContentVersion(
            id=version_id,
            content_item_id=item_id,
            version_number=1,
            payload_json=row,
            evidence_ids=ev_ids if ev_ids else None,
            change_summary="Bulk import",
            content_hash=rr.content_hash,
            source_file_name=fname,
            source_row_number=rr.row_number,
            created_by=actor.id,
            is_current=True,
        )

        db.add(item)
        db.add(version)
        created_items += 1
        created_versions += 1

        # Track newly seen external_id to prevent double-creates within this batch
        existing_ext_ids.add(rr.external_id)
        existing_hashes.add(rr.content_hash)

    # --- Commit evidence sources ---
    created_evidence = 0
    ev_urls_to_check = [row.get("url", "").strip() for _, row in all_valid_evidence]
    existing_ev_urls = await _db_duplicate_evidence_urls(db, ev_urls_to_check)

    for _, row in all_valid_evidence:
        url = row.get("url", "").strip()
        if url in existing_ev_urls:
            skipped += 1
            continue

        raw_region = row.get("region", "").strip()
        ev_region = _normalize_evidence_region(raw_region) or raw_region or None

        source = EvidenceSource(
            title=row.get("source_name", "").strip(),
            organization=row.get("source_name", "").strip(),
            source_type=row.get("source_type", "").strip() or None,
            url=url or None,
            region=ev_region,
            evidence_status="active",
            notes=json.dumps({
                "evidence_id": row.get("evidence_id", "").strip(),
                "coverage": row.get("coverage", "").strip(),
                "review_frequency": row.get("review_frequency", "").strip(),
                "use_in_content": row.get("use_in_content", "").strip(),
            }),
        )
        db.add(source)
        created_evidence += 1
        existing_ev_urls.add(url)

    # --- Commit localization/region rules ---
    created_rules = 0
    loc_region_codes = []
    for _, row in all_valid_localization:
        raw = row.get("region", "").strip()
        norm = _REGION_NORM.get(raw.lower())
        if norm and norm in _VALID_LEARNER_REGIONS:
            loc_region_codes.append(norm)

    existing_rule_regions = await _db_duplicate_region_rules(db, loc_region_codes)

    for _, row in all_valid_localization:
        raw = row.get("region", "").strip()
        norm = _REGION_NORM.get(raw.lower())
        if not norm or norm not in _VALID_LEARNER_REGIONS:
            continue
        if norm in existing_rule_regions:
            skipped += 1
            continue
        rule = RegionPublishingRule(
            region_code=norm,
            content_type=None,
            domain=None,
            requires_local_disclaimer=True,
            requires_protocol_note=True,
            is_active=False,  # inactive until an admin reviews and activates
        )
        db.add(rule)
        created_rules += 1
        existing_rule_regions.add(norm)

    # Reference-only file warnings
    for fr in file_results:
        if fr.is_reference and not fr.file_name.endswith(".json"):
            warnings.append(
                f"{fr.file_name}: parsed as reference-only ({fr.total_rows} rows); "
                "not imported as learner content"
            )

    # Update ImportBatch counters
    import_batch.total_rows = sum(fr.total_rows for fr in file_results if not fr.is_reference)
    import_batch.valid_rows = created_items + created_evidence + created_rules
    import_batch.invalid_rows = invalid_count
    import_batch.created_items = created_items
    import_batch.created_versions = created_versions
    import_batch.created_evidence_sources = created_evidence
    import_batch.created_region_rules = created_rules
    import_batch.skipped_duplicates = skipped
    import_batch.warnings_json = warnings[:50]

    await log_action(
        db,
        action="content.bulk_import_committed",
        actor_user_id=actor.id,
        resource_type="import_batch",
        resource_id=str(import_batch.id),
        details={
            "source_file": os.path.basename(file_name),
            "created_items": created_items,
            "created_versions": created_versions,
            "created_evidence_sources": created_evidence,
            "created_region_rules": created_rules,
            "skipped_duplicates": skipped,
            "invalid_rows": invalid_count,
        },
    )

    await db.commit()

    return CommitResult(
        import_batch_id=str(import_batch.id),
        created_items=created_items,
        created_versions=created_versions,
        created_evidence_sources=created_evidence,
        created_region_rules=created_rules,
        skipped_duplicates=skipped,
        invalid_rows=invalid_count,
        warnings=warnings,
        approval_batch_id=str(approval_batch_id) if approval_batch_id else None,
        row_errors=row_errors_out[:100],
    )
