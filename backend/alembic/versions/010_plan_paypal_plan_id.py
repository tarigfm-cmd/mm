"""Add external_paypal_plan_id to subscription_plans

Revision ID: 010
Revises: 009
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscription_plans",
        sa.Column("external_paypal_plan_id", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscription_plans", "external_paypal_plan_id")
