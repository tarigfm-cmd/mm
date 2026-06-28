"""Billing and subscription management endpoints."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_superuser
from app.database import get_db
from app.models.billing import SubscriptionPlan, UserSubscription
from app.models.identity import User
from app.schemas.billing import (
    MonthlyUsageResponse,
    SubscriptionAssignRequest,
    SubscriptionPlanRead,
    UsageSummary,
    UserSubscriptionRead,
    UserSubscriptionWithFallback,
)
from app.services.entitlements import (
    count_monthly_usage,
    get_effective_plan,
    get_user_current_subscription,
)

router = APIRouter(prefix="/api/billing", tags=["billing"])

_METERED_EVENTS = [
    "training_session_started",
    "training_session_completed",
    "content_detail_viewed",
    "progress_viewed",
]


@router.get("/plans", response_model=list[SubscriptionPlanRead])
async def list_plans(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SubscriptionPlanRead]:
    """Return all active subscription plans."""
    rows = (
        await db.execute(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.is_active.is_(True))
            .order_by(SubscriptionPlan.price_monthly_cents)
        )
    ).scalars().all()
    return [SubscriptionPlanRead.model_validate(r) for r in rows]


@router.get("/me/subscription", response_model=UserSubscriptionWithFallback)
async def get_my_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserSubscriptionWithFallback:
    """Return the current user's subscription and effective plan (free fallback if none)."""
    sub = await get_user_current_subscription(db, current_user.id)
    plan = await get_effective_plan(db, current_user.id)

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No subscription plans found. Contact the platform administrator.",
        )

    return UserSubscriptionWithFallback(
        subscription=UserSubscriptionRead.model_validate(sub) if sub else None,
        plan=SubscriptionPlanRead.model_validate(plan),
        is_free_tier=sub is None,
    )


@router.get("/me/usage", response_model=MonthlyUsageResponse)
async def get_my_usage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MonthlyUsageResponse:
    """Return current month usage counts for the authenticated user."""
    plan = await get_effective_plan(db, current_user.id)

    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    usage_list: list[UsageSummary] = []
    for event_type in _METERED_EVENTS:
        count = await count_monthly_usage(db, current_user.id, event_type)
        limit: Optional[int] = None
        if plan and event_type == "training_session_started":
            limit = plan.max_training_sessions_per_month
        usage_list.append(
            UsageSummary(event_type=event_type, count=count, limit=limit)
        )

    return MonthlyUsageResponse(usage=usage_list, period_start=period_start)


@router.post("/admin/users/{user_id}/subscription", response_model=UserSubscriptionRead)
async def admin_assign_subscription(
    user_id: uuid.UUID,
    body: SubscriptionAssignRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_superuser),
) -> UserSubscriptionRead:
    """Assign or replace a user's subscription plan. Platform admin only."""
    target_user = await db.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    plan_row = (
        await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.code == body.plan_code).limit(1)
        )
    ).scalar_one_or_none()
    if plan_row is None:
        raise HTTPException(
            status_code=422, detail=f"Plan code '{body.plan_code}' not found."
        )

    # Cancel any existing active subscriptions
    existing = (
        await db.execute(
            select(UserSubscription).where(
                UserSubscription.user_id == user_id,
                UserSubscription.status.in_(["active", "trialing"]),
            )
        )
    ).scalars().all()
    for old_sub in existing:
        old_sub.status = "canceled"

    new_sub = UserSubscription(
        user_id=user_id,
        plan_id=plan_row.id,
        status=body.status,
        assigned_by=admin.id,
    )
    db.add(new_sub)
    await db.commit()
    await db.refresh(new_sub)

    return UserSubscriptionRead.model_validate(new_sub)
