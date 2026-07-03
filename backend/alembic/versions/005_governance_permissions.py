"""Seed governance permissions and assign them to roles

Revision ID: 005
Revises: 004
Create Date: 2026-06-27
"""
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

# (name, display_name, resource, action, description)
_PERMISSIONS = [
    ("content.import", "Import Content", "content", "import", "Create content items and initiate bulk import"),
    ("content.review", "Review Content", "content", "review", "Submit and read clinical reviews"),
    ("content.approve", "Approve Content", "content", "approve", "Submit approval-batch records"),
    ("content.publish", "Publish Content", "content", "publish", "Publish content items to regions"),
    ("content.unpublish", "Unpublish Content", "content", "unpublish", "Unpublish content from regions"),
    ("content.version.create", "Create Content Version", "content", "version.create", "Create new content versions"),
    ("content.rollback", "Rollback Content Version", "content", "rollback", "Roll back to a prior version"),
    ("evidence.manage", "Manage Evidence Sources", "evidence", "manage", "Create and update evidence sources"),
    ("analytics.view", "View Analytics", "analytics", "view", "View platform-level failure analytics"),
    ("analytics.view_org", "View Organization Analytics", "analytics", "view_org", "View analytics for a specific organization"),
]

# role_name → [permission_names]
_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "educator": [
        "content.import", "content.review", "content.version.create", "analytics.view",
    ],
    "content_reviewer": [
        "content.review", "content.approve", "content.version.create",
        "evidence.manage", "analytics.view",
    ],
    "institution_admin": [
        "content.import", "content.review", "content.approve",
        "content.publish", "content.unpublish", "content.version.create",
        "content.rollback", "evidence.manage", "analytics.view", "analytics.view_org",
    ],
    "platform_admin": [
        "content.import", "content.review", "content.approve",
        "content.publish", "content.unpublish", "content.version.create",
        "content.rollback", "evidence.manage", "analytics.view", "analytics.view_org",
    ],
}


def upgrade() -> None:
    # Insert permissions (idempotent — skip if already exists)
    for name, display_name, resource, action, description in _PERMISSIONS:
        op.execute(f"""
            INSERT INTO permissions (id, name, display_name, resource, action, description)
            SELECT gen_random_uuid(), '{name}', '{display_name}', '{resource}', '{action}', '{description}'
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE name = '{name}')
        """)

    # Assign permissions to roles (idempotent)
    for role_name, perm_names in _ROLE_PERMISSIONS.items():
        for perm_name in perm_names:
            op.execute(f"""
                INSERT INTO role_permissions (id, role_id, permission_id)
                SELECT gen_random_uuid(), r.id, p.id
                FROM roles r
                JOIN permissions p ON p.name = '{perm_name}'
                WHERE r.name = '{role_name}'
                AND NOT EXISTS (
                    SELECT 1 FROM role_permissions rp
                    WHERE rp.role_id = r.id AND rp.permission_id = p.id
                )
            """)


def downgrade() -> None:
    # Remove role_permission assignments for these permissions
    all_perm_names = ", ".join(f"'{n}'" for n, *_ in _PERMISSIONS)
    op.execute(f"""
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE name IN ({all_perm_names})
        )
    """)
    op.execute(f"""
        DELETE FROM permissions WHERE name IN ({all_perm_names})
    """)
