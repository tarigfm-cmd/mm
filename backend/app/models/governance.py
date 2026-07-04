"""
Content governance models: items, versions, evidence, approvals, publishing, analytics.

The circular FK between content_items.current_version_id and content_versions.id
is handled by use_alter=True — SQLAlchemy creates both tables first, then adds
the deferred constraint via ALTER TABLE (PostgreSQL) or omits it silently (SQLite).
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# ---------------------------------------------------------------------------
# Status / type string constants (plain strings preserve SQLite compatibility)
# ---------------------------------------------------------------------------

CONTENT_STATUSES = frozenset({
    "draft", "imported", "pending_review", "clinically_approved",
    "published", "unpublished", "needs_update", "retired",
})

CONTENT_TYPES = frozenset({
    "case", "simulation", "osce_station", "prescription_screening",
    "drill", "game", "evidence_source", "taxonomy_node",
})

REVIEW_DECISIONS = frozenset({
    "approved", "approved_with_conditions", "rejected", "needs_revision",
})

EVIDENCE_STATUSES = frozenset({
    "active", "needs_review", "superseded", "region_specific", "retired",
})

PUBLICATION_STATUSES = frozenset({"published", "unpublished", "rolled_back"})

REGION_CODES = frozenset({"UK", "US", "GCC", "AU"})
GLOBAL_SENTINEL = "GLOBAL"


# ---------------------------------------------------------------------------
# ContentItem
# ---------------------------------------------------------------------------

class ContentItem(Base):
    """Unified parent record for all educational content types."""

    __tablename__ = "content_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    specialty: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    difficulty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    region_scope: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft", index=True)
    # DEFERRABLE FK — checked at COMMIT, not at INSERT, to allow circular inserts
    # (content_items → content_versions and content_versions → content_items).
    # Migration 013 made this DEFERRABLE INITIALLY DEFERRED in PostgreSQL.
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey(
            "content_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_content_item_current_version_id",
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ────────────────────────────────────────────────────────
    versions: Mapped[list["ContentVersion"]] = relationship(
        "ContentVersion",
        foreign_keys="ContentVersion.content_item_id",
        back_populates="content_item",
        cascade="all, delete-orphan",
        order_by="ContentVersion.version_number",
    )
    reviews: Mapped[list["ClinicalReview"]] = relationship(
        "ClinicalReview", back_populates="content_item", cascade="all, delete-orphan"
    )
    publications: Mapped[list["PublicationRecord"]] = relationship(
        "PublicationRecord", back_populates="content_item", cascade="all, delete-orphan"
    )
    failure_analytics: Mapped[list["LearnerFailureAnalytics"]] = relationship(
        "LearnerFailureAnalytics", back_populates="content_item", cascade="all, delete-orphan"
    )
    creator: Mapped[Optional["User"]] = relationship(  # noqa: F821
        "User", foreign_keys=[created_by]
    )


# ---------------------------------------------------------------------------
# ContentVersion
# ---------------------------------------------------------------------------

class ContentVersion(Base):
    """Immutable snapshot of a ContentItem at a point in time."""

    __tablename__ = "content_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True), primary_key=True, default=uuid.uuid4
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [uuid strings]
    localization_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_file_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    content_item: Mapped["ContentItem"] = relationship(
        "ContentItem",
        foreign_keys=[content_item_id],
        back_populates="versions",
    )
    creator: Mapped[Optional["User"]] = relationship(  # noqa: F821
        "User", foreign_keys=[created_by]
    )
    reviews: Mapped[list["ClinicalReview"]] = relationship(
        "ClinicalReview", back_populates="content_version"
    )
    publications: Mapped[list["PublicationRecord"]] = relationship(
        "PublicationRecord", back_populates="content_version"
    )


# ---------------------------------------------------------------------------
# EvidenceSource
# ---------------------------------------------------------------------------

class EvidenceSource(Base):
    """Tracked external clinical evidence (guidelines, literature, protocols)."""

    __tablename__ = "evidence_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    region: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    evidence_status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# ApprovalBatch
# ---------------------------------------------------------------------------

class ApprovalBatch(Base):
    """Records a bulk external-reviewer approval covering multiple content items."""

    __tablename__ = "approval_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_package_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    approved_by_team_name: Mapped[str] = mapped_column(String(255), nullable=False)
    approval_statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    region_scope: Mapped[list | None] = mapped_column(JSON, nullable=True)
    content_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    reviews: Mapped[list["ClinicalReview"]] = relationship(
        "ClinicalReview", back_populates="approval_batch"
    )
    approver: Mapped[Optional["User"]] = relationship(  # noqa: F821
        "User", foreign_keys=[approved_by_user_id]
    )


# ---------------------------------------------------------------------------
# ClinicalReview
# ---------------------------------------------------------------------------

class ClinicalReview(Base):
    """Pharmacist team approval/sign-off record for a specific content item + version."""

    __tablename__ = "clinical_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True), primary_key=True, default=uuid.uuid4
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("content_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewer_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewer_team_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_reviewer_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approval_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("approval_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    review_decision: Mapped[str] = mapped_column(String(50), nullable=False)
    review_scope: Mapped[str | None] = mapped_column(String(255), nullable=True)
    clinical_accuracy_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    safety_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    localization_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_off_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    content_item: Mapped["ContentItem"] = relationship("ContentItem", back_populates="reviews")
    content_version: Mapped[Optional["ContentVersion"]] = relationship(
        "ContentVersion", back_populates="reviews"
    )
    approval_batch: Mapped[Optional["ApprovalBatch"]] = relationship(
        "ApprovalBatch", back_populates="reviews"
    )
    reviewer: Mapped[Optional["User"]] = relationship(  # noqa: F821
        "User", foreign_keys=[reviewer_user_id]
    )


# ---------------------------------------------------------------------------
# RegionPublishingRule
# ---------------------------------------------------------------------------

class RegionPublishingRule(Base):
    """Per-region, per-content-type publishing requirements and constraints."""

    __tablename__ = "region_publishing_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True), primary_key=True, default=uuid.uuid4
    )
    region_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    content_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    allowed_statuses: Mapped[list | None] = mapped_column(JSON, nullable=True)
    required_review_roles: Mapped[list | None] = mapped_column(JSON, nullable=True)
    required_evidence_region: Mapped[str | None] = mapped_column(String(10), nullable=True)
    requires_local_disclaimer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_protocol_note: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# PublicationRecord
# ---------------------------------------------------------------------------

class PublicationRecord(Base):
    """Tracks where and when a specific ContentVersion was published."""

    __tablename__ = "publication_records"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True), primary_key=True, default=uuid.uuid4
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("content_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    region_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    unpublished_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    unpublished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publication_status: Mapped[str] = mapped_column(String(50), nullable=False, default="published")
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rollback_from_publication_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("publication_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    content_item: Mapped["ContentItem"] = relationship("ContentItem", back_populates="publications")
    content_version: Mapped["ContentVersion"] = relationship(
        "ContentVersion", back_populates="publications"
    )
    publisher: Mapped[Optional["User"]] = relationship(  # noqa: F821
        "User", foreign_keys=[published_by]
    )
    unpublisher: Mapped[Optional["User"]] = relationship(  # noqa: F821
        "User", foreign_keys=[unpublished_by]
    )


# ---------------------------------------------------------------------------
# LearnerFailureAnalytics
# ---------------------------------------------------------------------------

class LearnerFailureAnalytics(Base):
    """
    Content-version-aware failure analytics.

    Separate from Interaction because:
    - Interaction has no content_version_id (links to scenarios, not content items)
    - Requires specific failure-type columns absent from Interaction
    - Needs region_code and organization_id for geographic analytics
    """

    __tablename__ = "learner_failure_analytics"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True), primary_key=True, default=uuid.uuid4
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("content_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    region_code: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    attempt_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    failed_red_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_counseling_point: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_interaction_detection: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_referral_decision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_dose_calculation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_documentation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    time_to_decision_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    content_item: Mapped["ContentItem"] = relationship(
        "ContentItem", back_populates="failure_analytics"
    )


# ---------------------------------------------------------------------------
# ImportBatch
# ---------------------------------------------------------------------------

class ImportBatch(Base):
    """Tracks a single bulk import operation for audit and traceability."""

    __tablename__ = "import_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    package_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "csv" or "zip"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="previewed")
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approval_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("approval_batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_versions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_evidence_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_region_rules: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_duplicates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    errors_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    uploader: Mapped[Optional["User"]] = relationship(  # noqa: F821
        "User", foreign_keys=[uploaded_by_user_id]
    )
    row_errors: Mapped[list["ImportRowError"]] = relationship(
        "ImportRowError", back_populates="import_batch", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# ImportRowError
# ---------------------------------------------------------------------------

class ImportRowError(Base):
    """Per-row error record created during commit for import traceability."""

    __tablename__ = "import_row_errors"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True), primary_key=True, default=uuid.uuid4
    )
    import_batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="error")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    import_batch: Mapped["ImportBatch"] = relationship(
        "ImportBatch", back_populates="row_errors"
    )


# ---------------------------------------------------------------------------
# LearnerTrainingSession
# ---------------------------------------------------------------------------

class LearnerTrainingSession(Base):
    """Tracks a single guided training session for one learner on one content item."""

    __tablename__ = "learner_training_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("content_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True, native_uuid=True),
        ForeignKey("content_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    region_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="started", index=True
    )  # "started" | "completed" | "abandoned"
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    score_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    failed_dimensions_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    not_assessable_dimensions_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    learner_responses_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    feedback_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])  # noqa: F821
    content_item: Mapped["ContentItem"] = relationship(
        "ContentItem", foreign_keys=[content_item_id]
    )
    content_version: Mapped["ContentVersion"] = relationship(
        "ContentVersion", foreign_keys=[content_version_id]
    )
