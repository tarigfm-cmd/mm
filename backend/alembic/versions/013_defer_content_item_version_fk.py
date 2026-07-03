"""Make fk_content_item_current_version_id DEFERRABLE INITIALLY DEFERRED

PostgreSQL enforces FK constraints immediately (at INSERT time) by default.
content_items.current_version_id → content_versions.id forms a circular
dependency with content_versions.content_item_id → content_items.id.

During a bulk import, SQLAlchemy inserts content_items before content_versions
(because content_versions depends on content_items.id, not the reverse), which
means current_version_id always points to a version that does not exist yet at
INSERT time. Making this FK DEFERRABLE INITIALLY DEFERRED moves the check to
COMMIT time, by which point both rows exist.

SQLite does not enforce FK constraints by default so the original immediate FK
was invisible in the SQLite test suite.

Revision ID: 013
Revises: 012
Create Date: 2026-07-03
"""
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_content_item_current_version_id",
        "content_items",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_content_item_current_version_id",
        "content_items",
        "content_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_content_item_current_version_id",
        "content_items",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_content_item_current_version_id",
        "content_items",
        "content_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
