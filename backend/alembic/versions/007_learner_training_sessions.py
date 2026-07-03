"""Add LearnerTrainingSession table for guided training engine

Revision ID: 007
Revises: 006
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learner_training_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "content_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_items.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "content_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_versions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("region_code", sa.String(10), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="started", index=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_step", sa.Integer, nullable=False, server_default="1"),
        sa.Column("total_steps", sa.Integer, nullable=False, server_default="1"),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("max_score", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("score_percent", sa.Float, nullable=True),
        sa.Column("failed_dimensions_json", postgresql.JSON, nullable=True),
        sa.Column("not_assessable_dimensions_json", postgresql.JSON, nullable=True),
        sa.Column("learner_responses_json", postgresql.JSON, nullable=True),
        sa.Column("feedback_json", postgresql.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("learner_training_sessions")
