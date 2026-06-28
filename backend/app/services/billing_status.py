"""Safe PayPal configuration status builder.

Pure function — takes Settings and a list of SubscriptionPlan ORM rows.
Never reads secrets; only inspects boolean presence of credential fields.
"""
from typing import TYPE_CHECKING

from app.schemas.billing import PayPalConfigStatus, PayPalPlanStatus

if TYPE_CHECKING:
    from app.config import Settings
    from app.models.billing import SubscriptionPlan


def build_paypal_config_status(
    settings: "Settings",
    plans: "list[SubscriptionPlan]",
) -> PayPalConfigStatus:
    """Build a safe PayPal configuration readiness report.

    Returns boolean presence indicators for each credential; never the values.
    """
    client_id_ok = bool(settings.paypal_client_id)
    client_secret_ok = bool(settings.paypal_client_secret)
    webhook_id_ok = bool(settings.paypal_webhook_id)
    paypal_configured = client_id_ok and client_secret_ok

    webhook_url = f"{settings.app_public_url}/api/billing/webhooks/paypal"
    success_url = f"{settings.app_public_url}/billing/success"
    cancel_url = f"{settings.app_public_url}/billing/cancel"

    missing: list[str] = []
    warnings: list[str] = []

    if not client_id_ok:
        missing.append("PAYPAL_CLIENT_ID is not set")
    if not client_secret_ok:
        missing.append("PAYPAL_CLIENT_SECRET is not set")
    if not webhook_id_ok:
        missing.append("PAYPAL_WEBHOOK_ID is not set — incoming webhooks will be rejected")

    if settings.paypal_skip_webhook_verify:
        warnings.append(
            "PAYPAL_SKIP_WEBHOOK_VERIFY=true — webhook signature verification is disabled "
            "(development/test mode only; must be false in production)"
        )
    if settings.paypal_env == "live":
        warnings.append("PAYPAL_ENV=live — live payments are active")

    plan_statuses: list[PayPalPlanStatus] = []
    for plan in plans:
        is_paid = plan.price_monthly_cents > 0
        paypal_id_ok = bool(plan.external_paypal_plan_id)
        checkout_ready = paypal_configured and is_paid and paypal_id_ok and plan.is_active
        plan_statuses.append(
            PayPalPlanStatus(
                plan_code=plan.code,
                name=plan.name,
                is_active=plan.is_active,
                is_paid=is_paid,
                external_paypal_plan_id_configured=paypal_id_ok,
                checkout_ready=checkout_ready,
            )
        )

    return PayPalConfigStatus(
        paypal_env=settings.paypal_env,
        app_public_url=settings.app_public_url,
        client_id_configured=client_id_ok,
        client_secret_configured=client_secret_ok,
        webhook_id_configured=webhook_id_ok,
        paypal_configured=paypal_configured,
        webhook_url=webhook_url,
        success_url=success_url,
        cancel_url=cancel_url,
        plans=plan_statuses,
        missing_requirements=missing,
        warnings=warnings,
    )
