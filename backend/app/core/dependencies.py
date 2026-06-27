"""
Reusable FastAPI dependencies for authentication and authorisation.
"""
import uuid
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_token
from app.database import get_db

_bearer = HTTPBearer(auto_error=True)
_bearer_optional = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: AsyncSession = Depends(get_db),
):
    """
    Decode the Bearer JWT and load the corresponding User from the database.

    Raises HTTP 401 for any auth failure.
    """
    from app.models.identity import User  # local import avoids circular dependency

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = decode_token(credentials.credentials)
        subject: str = claims.get("sub", "")
        if not subject:
            raise credentials_exception
        token_type = claims.get("type", "")
        if token_type != "access":
            raise credentials_exception
    except ValueError:
        raise credentials_exception

    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise credentials_exception

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_optional_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer_optional)] = None,
    db: AsyncSession = Depends(get_db),
):
    """Like get_current_user but returns None instead of raising 401 when unauthenticated."""
    if credentials is None:
        return None
    from app.models.identity import User

    try:
        claims = decode_token(credentials.credentials)
        subject: str = claims.get("sub", "")
        if not subject or claims.get("type") != "access":
            return None
        user_id = uuid.UUID(subject)
    except Exception:
        return None

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


async def get_current_active_user(
    current_user=Depends(get_current_user),
):
    """Alias that enforces is_active — same as get_current_user but explicit."""
    return current_user


async def require_superuser(
    current_user=Depends(get_current_user),
):
    """Raise HTTP 403 unless the current user is a platform admin (is_superuser)."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator access required.",
        )
    return current_user


def require_org_role(required_role_name: str):
    """
    Return a FastAPI dependency that checks the user has *required_role_name*
    in *organization_id* (path param).

    Usage::
        @router.get("/{org_id}/members")
        async def list_members(
            org_id: uuid.UUID,
            user = Depends(require_org_role("institution_admin")),
        ): ...
    """
    async def _check(
        org_id: uuid.UUID,
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        from app.models.identity import OrganizationMembership, Role

        if current_user.is_superuser:
            return current_user

        result = await db.execute(
            select(OrganizationMembership)
            .where(
                OrganizationMembership.user_id == current_user.id,
                OrganizationMembership.organization_id == org_id,
                OrganizationMembership.is_active.is_(True),
            )
            .options(selectinload(OrganizationMembership.role))
        )
        membership = result.scalar_one_or_none()
        if membership is None or membership.role.name != required_role_name:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role_name}' required within this organization.",
            )
        return current_user

    return _check


async def get_user_org_membership(
    org_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Load and return the active OrganizationMembership for the current user
    in *org_id*. Raises HTTP 403 if no active membership exists (platform
    admins bypass this check).
    """
    from app.models.identity import OrganizationMembership

    if current_user.is_superuser:
        return None

    result = await db.execute(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == current_user.id,
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.is_active.is_(True),
        )
        .options(selectinload(OrganizationMembership.role))
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization.",
        )
    return membership


def require_content_permission(permission_name: str):
    """
    Platform-scoped permission check: the user must have *permission_name* in
    ANY of their active org memberships. Platform admins (is_superuser) bypass.

    Use this for governance endpoints that are not scoped to a specific org
    (content items, versions, evidence sources, platform-wide analytics).
    For org-scoped endpoints use has_permission() which reads org_id from the path.
    """
    async def _check(
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        if current_user.is_superuser:
            return current_user

        from app.models.identity import OrganizationMembership, Permission, RolePermission

        result = await db.execute(
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(OrganizationMembership, OrganizationMembership.role_id == RolePermission.role_id)
            .where(
                OrganizationMembership.user_id == current_user.id,
                OrganizationMembership.is_active.is_(True),
                Permission.name == permission_name,
            )
            .limit(1)
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission_name}' required.",
            )
        return current_user

    return _check


def has_permission(permission_name: str):
    """
    Return a dependency that checks whether the current user's role (within
    the *org_id* path param) includes *permission_name*.

    Platform admins bypass permission checks.
    """
    async def _check(
        org_id: uuid.UUID,
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        from app.models.identity import OrganizationMembership, RolePermission, Permission

        if current_user.is_superuser:
            return current_user

        result = await db.execute(
            select(OrganizationMembership)
            .where(
                OrganizationMembership.user_id == current_user.id,
                OrganizationMembership.organization_id == org_id,
                OrganizationMembership.is_active.is_(True),
            )
        )
        membership = result.scalar_one_or_none()
        if membership is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member.")

        perm_result = await db.execute(
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(
                RolePermission.role_id == membership.role_id,
                Permission.name == permission_name,
            )
        )
        if perm_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission_name}' required.",
            )
        return current_user

    return _check
