"""Append-only audit log writer for identity and org actions."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import AuditLog


async def log_action(
    db: AsyncSession,
    *,
    action: str,
    actor_user_id: Optional[uuid.UUID] = None,
    organization_id: Optional[uuid.UUID] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Add an immutable audit record to the current session.

    Never pass passwords, raw token values, or other secrets in *details*.
    The caller owns the commit boundary — this function does not flush or commit.
    """
    db.add(
        AuditLog(
            user_id=actor_user_id,
            organization_id=organization_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            extra_data=details,
            ip_address=ip_address,
        )
    )
