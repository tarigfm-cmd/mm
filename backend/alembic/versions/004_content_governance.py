"""Content governance tables: items, versions, evidence, approvals, publishing, analytics

Revision ID: 004
Revises: 003
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── content_items (without the deferred FK to content_versions) ────────────
    op.create_table(
        "content_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("domain", sa.String(100), nullable=True),
        sa.Column("specialty", sa.String(100), nullable=True),
        sa.Column("difficulty", sa.String(50), nullable=True),
        sa.Column("region_scope", postgresql.JSON, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_content_items_external_id", "content_items", ["external_id"])
    op.create_index("ix_content_items_content_type", "content_items", ["content_type"])
    op.create_index("ix_content_items_domain", "content_items", ["domain"])
    op.create_index("ix_content_items_specialty", "content_items", ["specialty"])
    op.create_index("ix_content_items_status", "content_items", ["status"])
    op.create_index("ix_content_items_created_by", "content_items", ["created_by"])

    # ── content_versions ───────────────────────────────────────────────────────
    op.create_table(
        "content_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("payload_json", postgresql.JSON, nullable=True),
        sa.Column("evidence_ids", postgresql.JSON, nullable=True),
        sa.Column("localization_notes", sa.Text, nullable=True),
        sa.Column("change_summary", sa.String(1000), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("source_file_name", sa.String(500), nullable=True),
        sa.Column("source_row_number", sa.Integer, nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_content_versions_content_item_id", "content_versions", ["content_item_id"])
    op.create_index("ix_content_versions_created_by", "content_versions", ["created_by"])
    op.create_index("ix_content_versions_content_hash", "content_versions", ["content_hash"])

    # ── Deferred FK: content_items.current_version_id → content_versions.id ───
    op.create_foreign_key(
        "fk_content_item_current_version_id",
        "content_items",
        "content_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ── evidence_sources ───────────────────────────────────────────────────────
    op.create_table(
        "evidence_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("organization", sa.String(255), nullable=True),
        sa.Column("source_type", sa.String(100), nullable=True),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("region", sa.String(10), nullable=True),
        sa.Column("publication_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_evidence_sources_region", "evidence_sources", ["region"])
    op.create_index("ix_evidence_sources_next_review_due_at", "evidence_sources", ["next_review_due_at"])

    # ── approval_batches ───────────────────────────────────────────────────────
    op.create_table(
        "approval_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("batch_name", sa.String(255), nullable=False),
        sa.Column("source_package_name", sa.String(500), nullable=True),
        sa.Column("approved_by_team_name", sa.String(255), nullable=False),
        sa.Column("approval_statement", sa.Text, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("region_scope", postgresql.JSON, nullable=True),
        sa.Column("content_count", sa.Integer, nullable=True),
        sa.Column("evidence_scope", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("signed_manifest_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )

    # ── clinical_reviews ───────────────────────────────────────────────────────
    op.create_table(
        "clinical_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewer_role", sa.String(100), nullable=True),
        sa.Column("reviewer_team_name", sa.String(255), nullable=True),
        sa.Column("external_reviewer_reference", sa.String(255), nullable=True),
        sa.Column("approval_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_decision", sa.String(50), nullable=False),
        sa.Column("review_scope", sa.String(255), nullable=True),
        sa.Column("clinical_accuracy_score", sa.Float, nullable=True),
        sa.Column("safety_score", sa.Float, nullable=True),
        sa.Column("localization_score", sa.Float, nullable=True),
        sa.Column("comments", sa.Text, nullable=True),
        sa.Column("signed_off_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_version_id"], ["content_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approval_batch_id"], ["approval_batches.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_clinical_reviews_content_item_id", "clinical_reviews", ["content_item_id"])
    op.create_index("ix_clinical_reviews_content_version_id", "clinical_reviews", ["content_version_id"])
    op.create_index("ix_clinical_reviews_approval_batch_id", "clinical_reviews", ["approval_batch_id"])

    # ── region_publishing_rules ────────────────────────────────────────────────
    op.create_table(
        "region_publishing_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("region_code", sa.String(10), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=True),
        sa.Column("domain", sa.String(100), nullable=True),
        sa.Column("allowed_statuses", postgresql.JSON, nullable=True),
        sa.Column("required_review_roles", postgresql.JSON, nullable=True),
        sa.Column("required_evidence_region", sa.String(10), nullable=True),
        sa.Column("requires_local_disclaimer", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("requires_protocol_note", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_region_publishing_rules_region_code", "region_publishing_rules", ["region_code"])

    # ── publication_records ────────────────────────────────────────────────────
    op.create_table(
        "publication_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("region_code", sa.String(10), nullable=False),
        sa.Column("published_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("unpublished_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unpublished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publication_status", sa.String(50), nullable=False, server_default="published"),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("rollback_from_publication_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_version_id"], ["content_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["unpublished_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rollback_from_publication_id"], ["publication_records.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_publication_records_content_item_id", "publication_records", ["content_item_id"])
    op.create_index("ix_publication_records_content_version_id", "publication_records", ["content_version_id"])
    op.create_index("ix_publication_records_region_code", "publication_records", ["region_code"])
    # Composite index for the publish/unpublish lookup query
    op.create_index(
        "ix_publication_records_item_region_status",
        "publication_records",
        ["content_item_id", "region_code", "publication_status"],
    )

    # ── learner_failure_analytics ──────────────────────────────────────────────
    op.create_table(
        "learner_failure_analytics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("region_code", sa.String(10), nullable=True),
        sa.Column("attempt_type", sa.String(50), nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("failed_red_flag", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("failed_counseling_point", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("failed_interaction_detection", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("failed_referral_decision", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("failed_dose_calculation", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("failed_documentation", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("time_to_decision_seconds", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_version_id"], ["content_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_learner_failure_analytics_content_item_id", "learner_failure_analytics", ["content_item_id"])
    op.create_index("ix_learner_failure_analytics_content_version_id", "learner_failure_analytics", ["content_version_id"])
    op.create_index("ix_learner_failure_analytics_user_id", "learner_failure_analytics", ["user_id"])
    op.create_index("ix_learner_failure_analytics_organization_id", "learner_failure_analytics", ["organization_id"])
    op.create_index("ix_learner_failure_analytics_region_code", "learner_failure_analytics", ["region_code"])
    op.create_index("ix_learner_failure_analytics_created_at", "learner_failure_analytics", ["created_at"])
    # Composite for time-series analytics by content item
    op.create_index(
        "ix_learner_failure_analytics_item_created",
        "learner_failure_analytics",
        ["content_item_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("learner_failure_analytics")
    op.drop_table("publication_records")
    op.drop_table("region_publishing_rules")
    op.drop_table("clinical_reviews")
    op.drop_table("approval_batches")
    op.drop_table("evidence_sources")
    op.drop_constraint("fk_content_item_current_version_id", "content_items", type_="foreignkey")
    op.drop_table("content_versions")
    op.drop_table("content_items")
