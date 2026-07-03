"""Subscription entitlement service.

Determines what actions a user is allowed based on their subscription plan
and usage within the current calendar month.

Platform admins (is_superuser=True) bypass all entitlement limits.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import SubscriptionPlan, UsageEvent, UserSubscription


async def get_user_current_subscription(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> Optional[UserSubscription]:
    result = await db.execute(
        select(UserSubscription)
        .where(
            UserSubscription.user_id == user_id,
            UserSubscription.status.in_(["active", "trialing"]),
        )
        .order_by(UserSubscription.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_plan_by_code(db: AsyncSession, code: str) -> Optional[SubscriptionPlan]:
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.code == code).limit(1)
    )
    return result.scalar_one_or_none()


async def get_effective_plan(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> Optional[SubscriptionPlan]:
    """Return user's current plan; falls back to free plan if no active subscription."""
    sub = await get_user_current_subscription(db, user_id)
    if sub is not None:
        return sub.plan
    return await _get_plan_by_code(db, "free")


async def count_monthly_usage(
    db: AsyncSession,
    user_id: uuid.UUID,
    event_type: str,
) -> int:
    """Count usage events of the given type in the current calendar month."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(func.count(UsageEvent.id)).where(
            UsageEvent.user_id == user_id,
            UsageEvent.event_type == event_type,
            UsageEvent.created_at >= month_start,
        )
    )
    return result.scalar_one() or 0


async def can_start_training_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    is_superuser: bool = False,
) -> tuple[bool, str]:
    """Return (allowed, reason). Admins always allowed. Returns 402-worthy reason on False."""
    if is_superuser:
        return True, ""

    plan = await get_effective_plan(db, user_id)
    if plan is None:
        return True, ""

    limit = plan.max_training_sessions_per_month
    if limit is None:
        return True, ""

    used = await count_monthly_usage(db, user_id, "training_session_started")
    if used >= limit:
        return False, "Training session limit reached for your current plan."
    return True, ""


async def record_usage_event(
    db: AsyncSession,
    user_id: uuid.UUID,
    event_type: str,
    *,
    organization_id: Optional[uuid.UUID] = None,
    content_item_id: Optional[uuid.UUID] = None,
    content_version_id: Optional[uuid.UUID] = None,
    metadata: Optional[dict] = None,
) -> UsageEvent:
    """Record a usage event. Caller is responsible for committing the transaction."""
    sub = await get_user_current_subscription(db, user_id)
    event = UsageEvent(
        user_id=user_id,
        organization_id=organization_id,
        subscription_id=sub.id if sub else None,
        event_type=event_type,
        content_item_id=content_item_id,
        content_version_id=content_version_id,
        metadata_json=metadata,
    )
    db.add(event)
    return event
