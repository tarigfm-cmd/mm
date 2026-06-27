"""Pydantic v2 schemas for content governance."""
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.governance import (
    CONTENT_STATUSES,
    CONTENT_TYPES,
    EVIDENCE_STATUSES,
    PUBLICATION_STATUSES,
    REGION_CODES,
    REVIEW_DECISIONS,
)

# ---------------------------------------------------------------------------
# ContentItem
# ---------------------------------------------------------------------------


class ContentItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content_type: str
    domain: Optional[str] = None
    specialty: Optional[str] = None
    difficulty: Optional[str] = None
    region_scope: Optional[list[str]] = None
    external_id: Optional[str] = None

    @field_validator("content_type", mode="before")
    @classmethod
    def valid_content_type(cls, v: str) -> str:
        if v not in CONTENT_TYPES:
            raise ValueError(f"content_type must be one of: {', '.join(sorted(CONTENT_TYPES))}")
        return v

    @field_validator("region_scope", mode="before")
    @classmethod
    def valid_regions(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            bad = [r for r in v if r not in REGION_CODES]
            if bad:
                raise ValueError(f"Invalid region codes: {bad}. Must be in {sorted(REGION_CODES)}")
        return v


class ContentItemRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    title: str
    content_type: str
    domain: Optional[str]
    specialty: Optional[str]
    difficulty: Optional[str]
    region_scope: Optional[list[str]]
    status: str
    external_id: Optional[str]
    current_version_id: Optional[uuid.UUID]
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    retired_at: Optional[datetime]


class ContentItemListItem(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    title: str
    content_type: str
    domain: Optional[str]
    specialty: Optional[str]
    difficulty: Optional[str]
    status: str
    region_scope: Optional[list[str]]
    current_version_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class ContentItemListResponse(BaseModel):
    items: list[ContentItemListItem]
    total: int
    page: int
    per_page: int
    pages: int


# ---------------------------------------------------------------------------
# ContentVersion
# ---------------------------------------------------------------------------


class ContentVersionCreate(BaseModel):
    payload_json: Optional[dict[str, Any]] = None
    evidence_ids: Optional[list[str]] = None
    localization_notes: Optional[str] = None
    change_summary: Optional[str] = Field(default=None, max_length=1000)
    source_file_name: Optional[str] = None
    source_row_number: Optional[int] = None


class ContentVersionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    content_item_id: uuid.UUID
    version_number: int
    payload_json: Optional[dict[str, Any]]
    evidence_ids: Optional[list[str]]
    localization_notes: Optional[str]
    change_summary: Optional[str]
    created_by: Optional[uuid.UUID]
    created_at: datetime
    is_current: bool
    source_file_name: Optional[str]
    source_row_number: Optional[int]
    content_hash: Optional[str]


# ---------------------------------------------------------------------------
# EvidenceSource
# ---------------------------------------------------------------------------


class EvidenceSourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    organization: Optional[str] = None
    source_type: Optional[str] = None
    url: Optional[str] = Field(default=None, max_length=2048)
    region: Optional[str] = None
    publication_date: Optional[datetime] = None
    next_review_due_at: Optional[datetime] = None
    evidence_status: str = "active"
    notes: Optional[str] = None

    @field_validator("evidence_status", mode="before")
    @classmethod
    def valid_evidence_status(cls, v: str) -> str:
        if v not in EVIDENCE_STATUSES:
            raise ValueError(f"evidence_status must be one of: {', '.join(sorted(EVIDENCE_STATUSES))}")
        return v

    @field_validator("region", mode="before")
    @classmethod
    def valid_region(cls, v: str | None) -> str | None:
        if v is not None and v not in REGION_CODES:
            raise ValueError(f"region must be one of: {sorted(REGION_CODES)}")
        return v


class EvidenceSourceUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    organization: Optional[str] = None
    source_type: Optional[str] = None
    url: Optional[str] = Field(default=None, max_length=2048)
    region: Optional[str] = None
    publication_date: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
    next_review_due_at: Optional[datetime] = None
    evidence_status: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("evidence_status", mode="before")
    @classmethod
    def valid_evidence_status(cls, v: str | None) -> str | None:
        if v is not None and v not in EVIDENCE_STATUSES:
            raise ValueError(f"evidence_status must be one of: {', '.join(sorted(EVIDENCE_STATUSES))}")
        return v

    @field_validator("region", mode="before")
    @classmethod
    def valid_region(cls, v: str | None) -> str | None:
        if v is not None and v not in REGION_CODES:
            raise ValueError(f"region must be one of: {sorted(REGION_CODES)}")
        return v


class EvidenceSourceRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    title: str
    organization: Optional[str]
    source_type: Optional[str]
    url: Optional[str]
    region: Optional[str]
    publication_date: Optional[datetime]
    last_checked_at: Optional[datetime]
    next_review_due_at: Optional[datetime]
    evidence_status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# ApprovalBatch
# ---------------------------------------------------------------------------


class ApprovalBatchCreate(BaseModel):
    batch_name: str = Field(min_length=1, max_length=255)
    source_package_name: Optional[str] = None
    approved_by_team_name: str = Field(min_length=1, max_length=255)
    approval_statement: Optional[str] = None
    approved_at: datetime
    region_scope: Optional[list[str]] = None
    content_count: Optional[int] = None
    evidence_scope: Optional[str] = None
    notes: Optional[str] = None
    signed_manifest_hash: Optional[str] = None

    @field_validator("region_scope", mode="before")
    @classmethod
    def valid_regions(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            bad = [r for r in v if r not in REGION_CODES]
            if bad:
                raise ValueError(f"Invalid region codes: {bad}. Must be in {sorted(REGION_CODES)}")
        return v


class ApprovalBatchRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    batch_name: str
    source_package_name: Optional[str]
    approved_by_team_name: str
    approval_statement: Optional[str]
    approved_at: datetime
    approved_by_user_id: Optional[uuid.UUID]
    region_scope: Optional[list[str]]
    content_count: Optional[int]
    evidence_scope: Optional[str]
    notes: Optional[str]
    signed_manifest_hash: Optional[str]
    created_at: datetime


# ---------------------------------------------------------------------------
# ClinicalReview
# ---------------------------------------------------------------------------


class ClinicalReviewCreate(BaseModel):
    content_version_id: Optional[uuid.UUID] = None
    reviewer_role: Optional[str] = None
    reviewer_team_name: Optional[str] = None
    external_reviewer_reference: Optional[str] = None
    approval_batch_id: Optional[uuid.UUID] = None
    review_decision: str
    review_scope: Optional[str] = None
    clinical_accuracy_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    safety_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    localization_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    comments: Optional[str] = None
    signed_off_at: Optional[datetime] = None
    review_due_at: Optional[datetime] = None

    @field_validator("review_decision", mode="before")
    @classmethod
    def valid_decision(cls, v: str) -> str:
        if v not in REVIEW_DECISIONS:
            raise ValueError(f"review_decision must be one of: {', '.join(sorted(REVIEW_DECISIONS))}")
        return v


class ClinicalReviewRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    content_item_id: uuid.UUID
    content_version_id: Optional[uuid.UUID]
    reviewer_user_id: Optional[uuid.UUID]
    reviewer_role: Optional[str]
    reviewer_team_name: Optional[str]
    external_reviewer_reference: Optional[str]
    approval_batch_id: Optional[uuid.UUID]
    review_decision: str
    review_scope: Optional[str]
    clinical_accuracy_score: Optional[float]
    safety_score: Optional[float]
    localization_score: Optional[float]
    comments: Optional[str]
    signed_off_at: Optional[datetime]
    review_due_at: Optional[datetime]
    created_at: datetime


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------


class PublishRequest(BaseModel):
    region_code: str
    reason: Optional[str] = None

    @field_validator("region_code", mode="before")
    @classmethod
    def valid_region(cls, v: str) -> str:
        if v not in REGION_CODES:
            raise ValueError(f"region_code must be one of: {sorted(REGION_CODES)}")
        return v


class UnpublishRequest(BaseModel):
    region_code: str
    reason: Optional[str] = None

    @field_validator("region_code", mode="before")
    @classmethod
    def valid_region(cls, v: str) -> str:
        if v not in REGION_CODES:
            raise ValueError(f"region_code must be one of: {sorted(REGION_CODES)}")
        return v


class PublicationRecordRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    content_item_id: uuid.UUID
    content_version_id: uuid.UUID
    region_code: str
    published_by: Optional[uuid.UUID]
    published_at: datetime
    unpublished_by: Optional[uuid.UUID]
    unpublished_at: Optional[datetime]
    publication_status: str
    reason: Optional[str]
    rollback_from_publication_id: Optional[uuid.UUID]
    created_at: datetime


# ---------------------------------------------------------------------------
# Failure Analytics
# ---------------------------------------------------------------------------


class FailureAnalyticsCreate(BaseModel):
    content_item_id: uuid.UUID
    content_version_id: Optional[uuid.UUID] = None
    organization_id: Optional[uuid.UUID] = None
    region_code: Optional[str] = None
    attempt_type: Optional[str] = None
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    failed_red_flag: bool = False
    failed_counseling_point: bool = False
    failed_interaction_detection: bool = False
    failed_referral_decision: bool = False
    failed_dose_calculation: bool = False
    failed_documentation: bool = False
    time_to_decision_seconds: Optional[int] = None

    @field_validator("region_code", mode="before")
    @classmethod
    def valid_region(cls, v: str | None) -> str | None:
        if v is not None and v not in REGION_CODES:
            raise ValueError(f"region_code must be one of: {sorted(REGION_CODES)}")
        return v


class FailureHotspot(BaseModel):
    content_item_id: uuid.UUID
    title: str
    content_type: str
    total_attempts: int
    avg_score: Optional[float]
    red_flag_fail_rate: float
    counseling_fail_rate: float
    interaction_fail_rate: float
    referral_fail_rate: float
    dose_calc_fail_rate: float
    documentation_fail_rate: float


class ContentFailureSummary(BaseModel):
    content_item_id: uuid.UUID
    title: str
    total_attempts: int
    avg_score: Optional[float]
    failure_breakdown: dict[str, float]
    version_breakdown: list[dict[str, Any]]


class OrgWeaknessMap(BaseModel):
    organization_id: uuid.UUID
    top_failure_types: list[str]
    failure_rates: dict[str, float]
    weak_domains: list[str]
    total_attempts: int
