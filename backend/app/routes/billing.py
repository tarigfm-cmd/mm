"""Billing and subscription management endpoints."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_superuser
from app.database import get_db
from app.models.billing import PaymentWebhookEvent, SubscriptionPlan, UserSubscription
from app.models.identity import User
from app.schemas.billing import (
    MonthlyUsageResponse,
    PayPalCheckoutRequest,
    PayPalCheckoutResponse,
    PayPalWebhookResponse,
    SubscriptionAssignRequest,
    SubscriptionPlanAdminRead,
    SubscriptionPlanRead,
    SubscriptionPlanUpdate,
    UsageSummary,
    UserSubscriptionRead,
    UserSubscriptionWithFallback,
)
from app.services.entitlements import (
    count_monthly_usage,
    get_effective_plan,
    get_user_current_subscription,
    record_usage_event,
)
from app.services.payment_providers.paypal import PayPalNotConfiguredError
from app.services.payment_providers.registry import get_paypal_provider

logger = logging.getLogger(__name__)

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


@router.get("/admin/plans", response_model=list[SubscriptionPlanAdminRead])
async def admin_list_plans(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_superuser),
) -> list[SubscriptionPlanAdminRead]:
    """Return all subscription plans including inactive ones. Superuser only."""
    rows = (
        await db.execute(
            select(SubscriptionPlan).order_by(SubscriptionPlan.price_monthly_cents)
        )
    ).scalars().all()
    return [SubscriptionPlanAdminRead.model_validate(r) for r in rows]


@router.patch("/admin/plans/{plan_code}", response_model=SubscriptionPlanAdminRead)
async def admin_update_plan(
    plan_code: str,
    body: SubscriptionPlanUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_superuser),
) -> SubscriptionPlanAdminRead:
    """Update plan fields including external_paypal_plan_id. Superuser only."""
    plan_row = (
        await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.code == plan_code).limit(1)
        )
    ).scalar_one_or_none()
    if plan_row is None:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_code}' not found.")

    if body.external_paypal_plan_id is not None and plan_row.price_monthly_cents == 0:
        raise HTTPException(
            status_code=422,
            detail="Free plans (price = 0) cannot have a PayPal Plan ID.",
        )
    # Also catch if price is being set to 0 while paypal id already exists or is being set
    new_price = body.price_monthly_cents if body.price_monthly_cents is not None else plan_row.price_monthly_cents
    new_paypal_id = body.external_paypal_plan_id if body.external_paypal_plan_id is not None else plan_row.external_paypal_plan_id
    if new_price == 0 and new_paypal_id:
        raise HTTPException(
            status_code=422,
            detail="Free plans (price = 0) cannot have a PayPal Plan ID.",
        )

    if body.name is not None:
        plan_row.name = body.name
    if body.price_monthly_cents is not None:
        plan_row.price_monthly_cents = body.price_monthly_cents
    if body.currency is not None:
        plan_row.currency = body.currency
    if body.is_active is not None:
        plan_row.is_active = body.is_active
    if "external_paypal_plan_id" in body.model_fields_set:
        plan_row.external_paypal_plan_id = body.external_paypal_plan_id

    await db.commit()
    await db.refresh(plan_row)
    return SubscriptionPlanAdminRead.model_validate(plan_row)


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


@router.post("/checkout/paypal", response_model=PayPalCheckoutResponse)
async def paypal_checkout(
    body: PayPalCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PayPalCheckoutResponse:
    """Initiate a PayPal checkout for the given plan. Returns an approval URL."""
    provider = get_paypal_provider()

    if not provider.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PayPal checkout is not configured yet. Contact admin for beta upgrade.",
        )

    plan_row = (
        await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.code == body.plan_code).limit(1)
        )
    ).scalar_one_or_none()
    if plan_row is None:
        raise HTTPException(status_code=404, detail=f"Plan '{body.plan_code}' not found.")
    if not plan_row.is_active:
        raise HTTPException(status_code=422, detail=f"Plan '{body.plan_code}' is not active.")
    if plan_row.price_monthly_cents == 0:
        raise HTTPException(
            status_code=422,
            detail="PayPal checkout is not available for the free plan.",
        )
    if not plan_row.external_paypal_plan_id:
        raise HTTPException(
            status_code=422,
            detail=f"PayPal checkout is not configured for the '{body.plan_code}' plan yet. Contact admin.",
        )

    from app.config import get_settings
    settings = get_settings()
    return_url = f"{settings.app_public_url}/billing/success"
    cancel_url = f"{settings.app_public_url}/billing/cancel"

    try:
        result = await provider.create_subscription(
            plan_code=body.plan_code,
            paypal_plan_id=plan_row.external_paypal_plan_id,
            price_monthly_cents=plan_row.price_monthly_cents,
            currency=plan_row.currency,
            user_id=str(current_user.id),
            return_url=return_url,
            cancel_url=cancel_url,
        )
    except PayPalNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PayPal checkout is not configured yet. Contact admin for beta upgrade.",
        )
    except Exception as exc:
        logger.error("PayPal checkout failed: %s", exc)
        raise HTTPException(status_code=502, detail="PayPal service error. Try again later.")

    await record_usage_event(
        db,
        user_id=current_user.id,
        event_type="billing_checkout_started",
        metadata={"plan_code": body.plan_code, "provider": "paypal"},
    )

    return PayPalCheckoutResponse(
        checkout_url=result.checkout_url,
        external_subscription_id=result.external_subscription_id,
        status=result.status,
        provider=result.provider,
    )


@router.post("/webhooks/paypal", response_model=PayPalWebhookResponse)
async def paypal_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PayPalWebhookResponse:
    """Receive and process PayPal webhook events."""
    raw_body = await request.body()
    headers = dict(request.headers)

    provider = get_paypal_provider()
    verify_result = await provider.verify_webhook(headers=headers, raw_body=raw_body)

    if not verify_result.verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook signature verification failed.",
        )

    # Idempotency: check if already processed
    existing = (
        await db.execute(
            select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.provider == "paypal",
                PaymentWebhookEvent.external_event_id == verify_result.external_event_id,
            ).limit(1)
        )
    ).scalar_one_or_none()

    if existing is not None:
        return PayPalWebhookResponse(status="already_processed")

    # Determine subscription status transition
    new_sub_status = provider.event_to_subscription_status(verify_result.event_type)

    webhook_event = PaymentWebhookEvent(
        provider="paypal",
        external_event_id=verify_result.external_event_id,
        event_type=verify_result.event_type,
        processed_status="pending",
        payload_summary_json=verify_result.payload_summary,
    )
    db.add(webhook_event)

    processing_error: Optional[str] = None

    if new_sub_status and verify_result.external_subscription_id:
        # Resolve user subscription
        user_sub = (
            await db.execute(
                select(UserSubscription).where(
                    UserSubscription.external_subscription_id == verify_result.external_subscription_id,
                    UserSubscription.external_provider == "paypal",
                ).limit(1)
            )
        ).scalar_one_or_none()

        if user_sub is None and verify_result.custom_id:
            # Fall back to resolving via custom_id (user_id we set at checkout)
            try:
                user_uuid = uuid.UUID(verify_result.custom_id)
                user_sub = (
                    await db.execute(
                        select(UserSubscription).where(
                            UserSubscription.user_id == user_uuid,
                            UserSubscription.status.in_(["active", "trialing", "past_due"]),
                        ).order_by(UserSubscription.created_at.desc()).limit(1)
                    )
                ).scalar_one_or_none()
            except ValueError:
                pass

        if user_sub is not None:
            user_sub.status = new_sub_status
            if verify_result.external_subscription_id:
                user_sub.external_subscription_id = verify_result.external_subscription_id
            user_sub.external_provider = "paypal"
            webhook_event.processed_status = "processed"
        else:
            webhook_event.processed_status = "unresolved"
            processing_error = (
                f"Could not resolve subscription for external_id="
                f"{verify_result.external_subscription_id} custom_id={verify_result.custom_id}"
            )
            logger.warning("PayPal webhook unresolved: %s", processing_error)
    else:
        webhook_event.processed_status = "processed"

    webhook_event.processing_error = processing_error
    webhook_event.processed_at = datetime.now(timezone.utc)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return PayPalWebhookResponse(status="already_processed")

    return PayPalWebhookResponse(
        status=webhook_event.processed_status,
        detail=processing_error,
    )
