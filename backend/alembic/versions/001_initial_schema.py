"""Initial schema — materials, scenarios, interactions

Revision ID: 001
Revises:
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("content_text", sa.Text, nullable=True),
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

    op.create_table(
        "scenarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("clinical_case", sa.Text, nullable=False),
        sa.Column("difficulty_level", sa.String(50), nullable=False, server_default="intermediate"),
        sa.Column("specialty", sa.String(100), nullable=True),
        sa.Column("key_concepts", postgresql.JSON, nullable=True),
        sa.Column("expected_answer", sa.Text, nullable=True),
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
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_scenarios_material_id", "scenarios", ["material_id"])
    op.create_index("ix_scenarios_difficulty_level", "scenarios", ["difficulty_level"])

    op.create_table(
        "interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scenario_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.String(255), nullable=True),
        sa.Column("user_answer", sa.Text, nullable=False),
        sa.Column("ai_feedback", sa.Text, nullable=False),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("key_findings", postgresql.JSON, nullable=True),
        sa.Column("next_steps", postgresql.JSON, nullable=True),
        sa.Column("strengths", postgresql.JSON, nullable=True),
        sa.Column("areas_for_improvement", postgresql.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_interactions_scenario_id", "interactions", ["scenario_id"])
    op.create_index("ix_interactions_session_id", "interactions", ["session_id"])


def downgrade() -> None:
    op.drop_table("interactions")
    op.drop_table("scenarios")
    op.drop_table("materials")
