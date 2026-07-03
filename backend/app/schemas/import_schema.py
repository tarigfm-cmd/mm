"""Pydantic schemas for the bulk CSV/ZIP import pipeline."""
import uuid
from typing import Any, Optional

from pydantic import BaseModel


class FileSummary(BaseModel):
    file_name: str
    content_type: Optional[str]  # None for reference-only files
    total_rows: int
    valid_rows: int
    invalid_rows: int
    skipped_duplicates: int
    is_reference_only: bool


class DuplicateSummary(BaseModel):
    duplicate_external_id_in_upload: int
    duplicate_hash_in_upload: int
    existing_external_id_in_db: int
    existing_hash_in_db: int


class RowError(BaseModel):
    file_name: str
    row_number: int
    external_id: Optional[str]
    error_code: str
    message: str
    severity: str = "error"


class PreviewResult(BaseModel):
    total_rows: int
    valid_rows: int
    invalid_rows: int
    warnings: list[str]
    errors_by_file: dict[str, list[str]]
    file_summaries: list[FileSummary]
    detected_content_types: list[str]
    duplicate_summary: DuplicateSummary
    approval_batch_required: bool
    row_errors: list[RowError] = []


class CommitResult(BaseModel):
    import_batch_id: str
    created_items: int
    created_versions: int
    created_evidence_sources: int
    created_region_rules: int
    skipped_duplicates: int
    invalid_rows: int
    warnings: list[str]
    approval_batch_id: Optional[str]
    row_errors: list[RowError] = []
