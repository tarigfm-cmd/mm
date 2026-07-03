"""Add ImportBatch and ImportRowError tables for import traceability

Revision ID: 006
Revises: 005
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_file_name", sa.String(500), nullable=False),
        sa.Column("package_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="previewed"),
        sa.Column(
            "uploaded_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "approval_batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("approval_batches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("total_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("valid_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("invalid_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_items", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_versions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_evidence_sources", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_region_rules", sa.Integer, nullable=False, server_default="0"),
        sa.Column("skipped_duplicates", sa.Integer, nullable=False, server_default="0"),
        sa.Column("warnings_json", postgresql.JSON, nullable=True),
        sa.Column("errors_json", postgresql.JSON, nullable=True),
        sa.Column("manifest_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "import_row_errors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "import_batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("import_batches.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("row_number", sa.Integer, nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="error"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("import_row_errors")
    op.drop_table("import_batches")
