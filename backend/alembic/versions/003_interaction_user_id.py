"""Add user_id to interactions table

Revision ID: 003
Revises: 002
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interactions",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_interactions_user_id", "interactions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_interactions_user_id", table_name="interactions")
    op.drop_column("interactions", "user_id")
