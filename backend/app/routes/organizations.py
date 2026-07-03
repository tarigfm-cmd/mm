"""
Organization management endpoints: create, list, update, member management.
"""
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user, require_superuser
from app.database import get_db
from app.models.identity import (
    Organization,
    OrganizationMembership,
    Role,
    RolePermission,
    User,
)
from app.schemas.identity import (
    AddMemberRequest,
    MemberRead,
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
    OrgWithRole,
    PermissionRead,
    RoleRead,
    UpdateMemberRoleRequest,
)
from app.services.audit import log_action

router = APIRouter(prefix="/api/orgs", tags=["organizations"])

ADMIN_ROLES = {"institution_admin", "platform_admin"}


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_active_org(slug: str, db: AsyncSession) -> Organization:
    result = await db.execute(
        select(Organization).where(Organization.slug == slug, Organization.is_active.is_(True))
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    return org


async def _get_membership(
    user: User, org: Organization, db: AsyncSession
) -> OrganizationMembership | None:
    result = await db.execute(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.is_active.is_(True),
        )
        .options(selectinload(OrganizationMembership.role))
    )
    return result.scalar_one_or_none()


async def _require_membership(
    user: User, org: Organization, db: AsyncSession
) -> OrganizationMembership | None:
    m = await _get_membership(user, org, db)
    if m is None and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization.",
        )
    return m


async def _require_admin(
    user: User, org: Organization, db: AsyncSession
) -> OrganizationMembership:
    if user.is_superuser:
        return None
    m = await _require_membership(user, org, db)
    if m.role.name not in ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization administrator role required.",
        )
    return m


async def _get_role_by_name(name: str, db: AsyncSession) -> Role:
    result = await db.execute(select(Role).where(Role.name == name))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{name}' does not exist.",
        )
    return role


async def _member_count(org_id, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).where(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.is_active.is_(True),
        )
    )
    return result.scalar_one()


# ── Roles endpoint ────────────────────────────────────────────────────────────


roles_router = APIRouter(prefix="/api/roles", tags=["roles"])


@roles_router.get("", response_model=List[RoleRead], summary="List all system roles")
async def list_roles(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> List[RoleRead]:
    result = await db.execute(
        select(Role)
        .where(Role.is_system_role.is_(True))
        .options(
            selectinload(Role.role_permissions).selectinload(RolePermission.permission)
        )
        .order_by(Role.name)
    )
    roles = result.scalars().all()
    return [
        RoleRead(
            id=r.id,
            name=r.name,
            display_name=r.display_name,
            description=r.description,
            is_system_role=r.is_system_role,
            permissions=[
                PermissionRead.model_validate(rp.permission)
                for rp in r.role_permissions
                if rp.permission is not None
            ],
        )
        for r in roles
    ]


# ── Organization CRUD ─────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=OrganizationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization",
)
async def create_org(
    body: OrganizationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> OrganizationRead:
    existing = await db.execute(select(Organization).where(Organization.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this slug already exists.",
        )

    org = Organization(name=body.name, slug=body.slug, org_type=body.org_type)
    db.add(org)
    await db.flush()  # get org.id

    admin_role = await _get_role_by_name("institution_admin", db)
    membership = OrganizationMembership(
        user_id=current_user.id,
        organization_id=org.id,
        role_id=admin_role.id,
    )
    db.add(membership)

    await log_action(
        db,
        action="org.create",
        actor_user_id=current_user.id,
        organization_id=org.id,
        resource_type="organization",
        resource_id=str(org.id),
        details={"name": org.name, "slug": org.slug, "org_type": org.org_type},
    )
    await db.commit()
    await db.refresh(org)
    return OrganizationRead.model_validate(org)


@router.get(
    "",
    response_model=List[OrgWithRole],
    summary="List current user's organizations",
)
async def list_my_orgs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> List[OrgWithRole]:
    result = await db.execute(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == current_user.id,
            OrganizationMembership.is_active.is_(True),
        )
        .options(
            selectinload(OrganizationMembership.organization),
            selectinload(OrganizationMembership.role),
        )
    )
    memberships = result.scalars().all()

    orgs = []
    for m in memberships:
        count = await _member_count(m.organization_id, db)
        orgs.append(
            OrgWithRole(
                id=m.organization.id,
                name=m.organization.name,
                slug=m.organization.slug,
                org_type=m.organization.org_type,
                is_active=m.organization.is_active,
                member_role=m.role.name,
                member_count=count,
                created_at=m.organization.created_at,
            )
        )
    return orgs


@router.get(
    "/{slug}",
    response_model=OrganizationRead,
    summary="Get organization details",
)
async def get_org(
    slug: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> OrganizationRead:
    org = await _get_active_org(slug, db)
    await _require_membership(current_user, org, db)
    return OrganizationRead.model_validate(org)


@router.patch(
    "/{slug}",
    response_model=OrganizationRead,
    summary="Update organization details (admin only)",
)
async def update_org(
    slug: str,
    body: OrganizationUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> OrganizationRead:
    org = await _get_active_org(slug, db)
    await _require_admin(current_user, org, db)

    if body.slug is not None and body.slug != org.slug:
        existing = await db.execute(select(Organization).where(Organization.slug == body.slug))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An organization with this slug already exists.",
            )
        org.slug = body.slug

    if body.name is not None:
        org.name = body.name
    if body.org_type is not None:
        org.org_type = body.org_type

    await log_action(
        db,
        action="org.update",
        actor_user_id=current_user.id,
        organization_id=org.id,
        resource_type="organization",
        resource_id=str(org.id),
        details={
            k: v for k, v in {"name": body.name, "slug": body.slug, "org_type": body.org_type}.items()
            if v is not None
        },
    )
    await db.commit()
    await db.refresh(org)
    return OrganizationRead.model_validate(org)


# ── Member management ─────────────────────────────────────────────────────────


@router.get(
    "/{slug}/members",
    response_model=List[MemberRead],
    summary="List organization members",
)
async def list_members(
    slug: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> List[MemberRead]:
    org = await _get_active_org(slug, db)
    await _require_membership(current_user, org, db)

    result = await db.execute(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.is_active.is_(True),
        )
        .options(
            selectinload(OrganizationMembership.user),
            selectinload(OrganizationMembership.role),
        )
        .order_by(OrganizationMembership.joined_at)
    )
    members = result.scalars().all()

    return [
        MemberRead(
            user_id=m.user.id,
            username=m.user.username,
            email=m.user.email,
            full_name=m.user.full_name,
            role_name=m.role.name,
            role_display_name=m.role.display_name,
            is_active=m.is_active,
            joined_at=m.joined_at,
        )
        for m in members
    ]


@router.post(
    "/{slug}/members",
    response_model=MemberRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a member to the organization (admin only)",
)
async def add_member(
    slug: str,
    body: AddMemberRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> MemberRead:
    org = await _get_active_org(slug, db)
    await _require_admin(current_user, org, db)

    result = await db.execute(select(User).where(User.email == body.email))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user found with that email address.",
        )

    existing = await db.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == target.id,
            OrganizationMembership.organization_id == org.id,
        )
    )
    existing_m = existing.scalar_one_or_none()
    role = await _get_role_by_name(body.role_name, db)

    if existing_m:
        if existing_m.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this organization.",
            )
        existing_m.role_id = role.id
        existing_m.is_active = True
        await db.flush()
        membership = existing_m
    else:
        membership = OrganizationMembership(
            user_id=target.id,
            organization_id=org.id,
            role_id=role.id,
        )
        db.add(membership)
        await db.flush()

    await log_action(
        db,
        action="org.member_added",
        actor_user_id=current_user.id,
        organization_id=org.id,
        resource_type="user",
        resource_id=str(target.id),
        details={"email": target.email, "role": role.name},
    )
    await db.commit()
    await db.refresh(membership)

    return MemberRead(
        user_id=target.id,
        username=target.username,
        email=target.email,
        full_name=target.full_name,
        role_name=role.name,
        role_display_name=role.display_name,
        is_active=membership.is_active,
        joined_at=membership.joined_at,
    )


@router.patch(
    "/{slug}/members/{member_user_id}",
    response_model=MemberRead,
    summary="Change a member's role (admin only)",
)
async def update_member_role(
    slug: str,
    member_user_id: str,
    body: UpdateMemberRoleRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> MemberRead:
    import uuid as _uuid

    org = await _get_active_org(slug, db)
    await _require_admin(current_user, org, db)

    try:
        target_id = _uuid.UUID(member_user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid user ID.")

    result = await db.execute(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == target_id,
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.is_active.is_(True),
        )
        .options(
            selectinload(OrganizationMembership.user),
            selectinload(OrganizationMembership.role),
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")

    old_role_name = membership.role.name
    role = await _get_role_by_name(body.role_name, db)
    membership.role_id = role.id

    await log_action(
        db,
        action="org.member_role_updated",
        actor_user_id=current_user.id,
        organization_id=org.id,
        resource_type="user",
        resource_id=str(target_id),
        details={"old_role": old_role_name, "new_role": role.name},
    )
    await db.commit()
    await db.refresh(membership)

    return MemberRead(
        user_id=membership.user.id,
        username=membership.user.username,
        email=membership.user.email,
        full_name=membership.user.full_name,
        role_name=role.name,
        role_display_name=role.display_name,
        is_active=membership.is_active,
        joined_at=membership.joined_at,
    )


@router.delete(
    "/{slug}/members/{member_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from the organization",
)
async def remove_member(
    slug: str,
    member_user_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    import uuid as _uuid

    org = await _get_active_org(slug, db)

    try:
        target_id = _uuid.UUID(member_user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid user ID.")

    if target_id != current_user.id:
        await _require_admin(current_user, org, db)

    result = await db.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == target_id,
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.is_active.is_(True),
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")

    membership.is_active = False

    await log_action(
        db,
        action="org.member_removed",
        actor_user_id=current_user.id,
        organization_id=org.id,
        resource_type="user",
        resource_id=str(target_id),
    )
    await db.commit()
