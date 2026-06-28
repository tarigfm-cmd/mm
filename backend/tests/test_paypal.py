"""Tests for PayPal checkout + webhook endpoints.

All tests use mocked PayPal provider — no real PayPal credentials required.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import PaymentWebhookEvent, SubscriptionPlan, UserSubscription
from app.models.identity import User
from app.services.payment_providers.base import CheckoutResult, WebhookVerifyResult
from app.services.payment_providers.paypal import PayPalProvider

# ---------------------------------------------------------------------------
# Helpers — shared with test_billing
# ---------------------------------------------------------------------------

VALID_USER = {
    "email": "pp_user@example.com",
    "username": "ppuser",
    "password": "PaypalPass1!",
    "full_name": "PayPal User",
}


async def _register_login(client: AsyncClient, user: dict) -> str:
    await client.post("/api/auth/register", json=user)
    r = await client.post(
        "/api/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    return r.json()["access_token"]


async def _seed_plans(
    session: AsyncSession, *, with_paypal_plan_id: bool = False
) -> dict[str, SubscriptionPlan]:
    """Seed test plans.

    Args:
        with_paypal_plan_id: If True, paid plans get a fake external_paypal_plan_id.
    """
    plans_data = [
        dict(code="free", name="Free", price_monthly_cents=0,
             max_training_sessions_per_month=20),
        dict(code="pro", name="Pro", price_monthly_cents=1999,
             max_training_sessions_per_month=1000,
             allows_osce=True, allows_games=True,
             external_paypal_plan_id="P-PRO-FAKE-001" if with_paypal_plan_id else None),
        dict(code="institution", name="Institution", price_monthly_cents=9900,
             external_paypal_plan_id="P-INST-FAKE-001" if with_paypal_plan_id else None),
    ]
    result: dict[str, SubscriptionPlan] = {}
    for data in plans_data:
        plan = SubscriptionPlan(**data)
        session.add(plan)
        result[data["code"]] = plan
    await session.commit()
    for p in result.values():
        await session.refresh(p)
    return result


def _mock_provider(
    *,
    configured: bool = True,
    checkout_url: str = "https://paypal.com/approve",
    sub_id: str = "SUB-123",
    verify_result: WebhookVerifyResult | None = None,
) -> MagicMock:
    provider = MagicMock(spec=PayPalProvider)
    provider.is_configured.return_value = configured
    provider.create_subscription = AsyncMock(
        return_value=CheckoutResult(
            checkout_url=checkout_url,
            external_subscription_id=sub_id,
            status="pending_redirect",
            provider="paypal",
        )
    )
    provider.verify_webhook = AsyncMock(return_value=verify_result or _verified_result())
    provider.event_to_subscription_status = PayPalProvider.event_to_subscription_status
    return provider


def _verified_result(
    *,
    verified: bool = True,
    event_type: str = "BILLING.SUBSCRIPTION.ACTIVATED",
    event_id: str = "EVT-001",
    resource_id: str = "SUB-123",
    custom_id: str | None = None,
) -> WebhookVerifyResult:
    return WebhookVerifyResult(
        verified=verified,
        event_type=event_type,
        external_event_id=event_id,
        external_subscription_id=resource_id,
        resource_status="ACTIVE",
        custom_id=custom_id,
        payload_summary={"event_type": event_type, "event_id": event_id},
    )


def _webhook_body(event_type: str = "BILLING.SUBSCRIPTION.ACTIVATED", event_id: str = "EVT-001") -> bytes:
    return json.dumps({
        "event_type": event_type,
        "id": event_id,
        "resource": {"id": "SUB-123", "status": "ACTIVE"},
    }).encode()


# ---------------------------------------------------------------------------
# POST /api/billing/checkout/paypal — unconfigured PayPal → 503
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkout_503_when_unconfigured(client: AsyncClient, fresh_engine: Any) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    token = await _register_login(client, VALID_USER)
    provider = _mock_provider(configured=False)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/checkout/paypal",
            json={"plan_code": "pro"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 503
    assert "not configured" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /api/billing/checkout/paypal — free plan → 422
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkout_422_for_free_plan(client: AsyncClient, fresh_engine: Any) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    token = await _register_login(client, VALID_USER)
    provider = _mock_provider(configured=True)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/checkout/paypal",
            json={"plan_code": "free"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/billing/checkout/paypal — unknown plan → 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkout_404_for_unknown_plan(client: AsyncClient, fresh_engine: Any) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    token = await _register_login(client, VALID_USER)
    provider = _mock_provider(configured=True)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/checkout/paypal",
            json={"plan_code": "nonexistent"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/billing/checkout/paypal — inactive plan → 422
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkout_422_for_inactive_plan(client: AsyncClient, fresh_engine: Any) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        plans = await _seed_plans(s)
        plans["pro"].is_active = False
        await s.commit()

    token = await _register_login(client, VALID_USER)
    provider = _mock_provider(configured=True)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/checkout/paypal",
            json={"plan_code": "pro"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/billing/checkout/paypal — success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkout_success_returns_url(client: AsyncClient, fresh_engine: Any) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s, with_paypal_plan_id=True)

    token = await _register_login(client, VALID_USER)
    provider = _mock_provider(configured=True, checkout_url="https://paypal.com/approve/xyz")

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/checkout/paypal",
            json={"plan_code": "pro"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["checkout_url"] == "https://paypal.com/approve/xyz"
    assert data["provider"] == "paypal"
    assert data["status"] == "pending_redirect"


# ---------------------------------------------------------------------------
# POST /api/billing/checkout/paypal — requires auth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkout_requires_auth(client: AsyncClient, fresh_engine: Any) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    r = await client.post("/api/billing/checkout/paypal", json={"plan_code": "pro"})
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /api/billing/webhooks/paypal — stores event idempotently
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_stores_event(client: AsyncClient, fresh_engine: Any) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    verify = _verified_result(event_id="EVT-STORE-1")
    provider = _mock_provider(verify_result=verify)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/webhooks/paypal",
            content=_webhook_body(event_id="EVT-STORE-1"),
            headers={"Content-Type": "application/json"},
        )

    assert r.status_code == 200

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        evt = (
            await s.execute(
                select(PaymentWebhookEvent).where(
                    PaymentWebhookEvent.external_event_id == "EVT-STORE-1"
                )
            )
        ).scalar_one_or_none()
    assert evt is not None
    assert evt.provider == "paypal"


# ---------------------------------------------------------------------------
# POST /api/billing/webhooks/paypal — duplicate → already_processed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_duplicate_returns_already_processed(
    client: AsyncClient, fresh_engine: Any
) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)
        # Pre-insert the webhook event
        s.add(PaymentWebhookEvent(
            provider="paypal",
            external_event_id="EVT-DUP-1",
            event_type="BILLING.SUBSCRIPTION.ACTIVATED",
            processed_status="processed",
            processed_at=datetime.now(timezone.utc),
        ))
        await s.commit()

    verify = _verified_result(event_id="EVT-DUP-1")
    provider = _mock_provider(verify_result=verify)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/webhooks/paypal",
            content=_webhook_body(event_id="EVT-DUP-1"),
            headers={"Content-Type": "application/json"},
        )

    assert r.status_code == 200
    assert r.json()["status"] == "already_processed"


# ---------------------------------------------------------------------------
# POST /api/billing/webhooks/paypal — ACTIVATED → subscription active
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_activated_sets_subscription_active(
    client: AsyncClient, fresh_engine: Any
) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        plans = await _seed_plans(s)
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="pp_webhook@example.com",
            username="ppwebhook",
            full_name="WH User",
            hashed_password="x",
        )
        s.add(user)
        sub = UserSubscription(
            user_id=user_id,
            plan_id=plans["pro"].id,
            status="trialing",
            external_provider="paypal",
            external_subscription_id="SUB-ACTIVATED-1",
        )
        s.add(sub)
        await s.commit()
        sub_db_id = sub.id

    verify = _verified_result(
        event_type="BILLING.SUBSCRIPTION.ACTIVATED",
        event_id="EVT-ACT-1",
        resource_id="SUB-ACTIVATED-1",
    )
    provider = _mock_provider(verify_result=verify)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/webhooks/paypal",
            content=_webhook_body("BILLING.SUBSCRIPTION.ACTIVATED", "EVT-ACT-1"),
            headers={"Content-Type": "application/json"},
        )

    assert r.status_code == 200

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        updated = await s.get(UserSubscription, sub_db_id)
    assert updated.status == "active"


# ---------------------------------------------------------------------------
# POST /api/billing/webhooks/paypal — CANCELLED → subscription canceled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_cancelled_sets_subscription_canceled(
    client: AsyncClient, fresh_engine: Any
) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        plans = await _seed_plans(s)
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="pp_cancel@example.com",
            username="ppcancel",
            full_name="Cancel User",
            hashed_password="x",
        )
        s.add(user)
        sub = UserSubscription(
            user_id=user_id,
            plan_id=plans["pro"].id,
            status="active",
            external_provider="paypal",
            external_subscription_id="SUB-CANCEL-1",
        )
        s.add(sub)
        await s.commit()
        sub_db_id = sub.id

    verify = _verified_result(
        event_type="BILLING.SUBSCRIPTION.CANCELLED",
        event_id="EVT-CAN-1",
        resource_id="SUB-CANCEL-1",
    )
    provider = _mock_provider(verify_result=verify)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/webhooks/paypal",
            content=_webhook_body("BILLING.SUBSCRIPTION.CANCELLED", "EVT-CAN-1"),
            headers={"Content-Type": "application/json"},
        )

    assert r.status_code == 200

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        updated = await s.get(UserSubscription, sub_db_id)
    assert updated.status == "canceled"


# ---------------------------------------------------------------------------
# POST /api/billing/webhooks/paypal — SUSPENDED → past_due
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_suspended_sets_past_due(
    client: AsyncClient, fresh_engine: Any
) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        plans = await _seed_plans(s)
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="pp_suspend@example.com",
            username="ppsuspend",
            full_name="Suspend User",
            hashed_password="x",
        )
        s.add(user)
        sub = UserSubscription(
            user_id=user_id,
            plan_id=plans["pro"].id,
            status="active",
            external_provider="paypal",
            external_subscription_id="SUB-SUSPEND-1",
        )
        s.add(sub)
        await s.commit()
        sub_db_id = sub.id

    verify = _verified_result(
        event_type="BILLING.SUBSCRIPTION.SUSPENDED",
        event_id="EVT-SUS-1",
        resource_id="SUB-SUSPEND-1",
    )
    provider = _mock_provider(verify_result=verify)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/webhooks/paypal",
            content=_webhook_body("BILLING.SUBSCRIPTION.SUSPENDED", "EVT-SUS-1"),
            headers={"Content-Type": "application/json"},
        )

    assert r.status_code == 200

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        updated = await s.get(UserSubscription, sub_db_id)
    assert updated.status == "past_due"


# ---------------------------------------------------------------------------
# POST /api/billing/webhooks/paypal — EXPIRED → expired
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_expired_sets_expired(
    client: AsyncClient, fresh_engine: Any
) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        plans = await _seed_plans(s)
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="pp_expire@example.com",
            username="ppexpire",
            full_name="Expire User",
            hashed_password="x",
        )
        s.add(user)
        sub = UserSubscription(
            user_id=user_id,
            plan_id=plans["pro"].id,
            status="active",
            external_provider="paypal",
            external_subscription_id="SUB-EXPIRE-1",
        )
        s.add(sub)
        await s.commit()
        sub_db_id = sub.id

    verify = _verified_result(
        event_type="BILLING.SUBSCRIPTION.EXPIRED",
        event_id="EVT-EXP-1",
        resource_id="SUB-EXPIRE-1",
    )
    provider = _mock_provider(verify_result=verify)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/webhooks/paypal",
            content=_webhook_body("BILLING.SUBSCRIPTION.EXPIRED", "EVT-EXP-1"),
            headers={"Content-Type": "application/json"},
        )

    assert r.status_code == 200

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        updated = await s.get(UserSubscription, sub_db_id)
    assert updated.status == "expired"


# ---------------------------------------------------------------------------
# POST /api/billing/webhooks/paypal — unresolved (no matching subscription)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_unresolved_stored_without_crash(
    client: AsyncClient, fresh_engine: Any
) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    verify = _verified_result(
        event_type="BILLING.SUBSCRIPTION.ACTIVATED",
        event_id="EVT-UNRES-1",
        resource_id="SUB-GHOST-99",
        custom_id=None,
    )
    provider = _mock_provider(verify_result=verify)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/webhooks/paypal",
            content=_webhook_body("BILLING.SUBSCRIPTION.ACTIVATED", "EVT-UNRES-1"),
            headers={"Content-Type": "application/json"},
        )

    assert r.status_code == 200

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        evt = (
            await s.execute(
                select(PaymentWebhookEvent).where(
                    PaymentWebhookEvent.external_event_id == "EVT-UNRES-1"
                )
            )
        ).scalar_one_or_none()
    assert evt is not None
    assert evt.processed_status == "unresolved"


# ---------------------------------------------------------------------------
# POST /api/billing/webhooks/paypal — invalid signature → 400
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_bad_signature_returns_400(
    client: AsyncClient, fresh_engine: Any
) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    verify = _verified_result(verified=False)
    provider = _mock_provider(verify_result=verify)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/webhooks/paypal",
            content=_webhook_body(),
            headers={"Content-Type": "application/json"},
        )

    assert r.status_code == 400


# ---------------------------------------------------------------------------
# PayPalProvider.event_to_subscription_status — unit tests
# ---------------------------------------------------------------------------

def test_event_to_status_activated() -> None:
    assert PayPalProvider.event_to_subscription_status("BILLING.SUBSCRIPTION.ACTIVATED") == "active"


def test_event_to_status_cancelled() -> None:
    assert PayPalProvider.event_to_subscription_status("BILLING.SUBSCRIPTION.CANCELLED") == "canceled"


def test_event_to_status_suspended() -> None:
    assert PayPalProvider.event_to_subscription_status("BILLING.SUBSCRIPTION.SUSPENDED") == "past_due"


def test_event_to_status_expired() -> None:
    assert PayPalProvider.event_to_subscription_status("BILLING.SUBSCRIPTION.EXPIRED") == "expired"


def test_event_to_status_unknown_returns_none() -> None:
    assert PayPalProvider.event_to_subscription_status("UNKNOWN.EVENT") is None


def test_event_to_status_none_returns_none() -> None:
    assert PayPalProvider.event_to_subscription_status(None) is None


# ---------------------------------------------------------------------------
# PayPalProvider.is_configured
# ---------------------------------------------------------------------------

def test_provider_configured_with_credentials() -> None:
    p = PayPalProvider(client_id="id", client_secret="secret", webhook_id="wh")
    assert p.is_configured() is True


def test_provider_not_configured_without_credentials() -> None:
    p = PayPalProvider(client_id="", client_secret="", webhook_id="")
    assert p.is_configured() is False


# ---------------------------------------------------------------------------
# PayPalProvider.verify_webhook — skip_verify mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_webhook_skip_verify_returns_verified() -> None:
    p = PayPalProvider(client_id="id", client_secret="secret", webhook_id="wh", skip_verify=True)
    body = json.dumps({
        "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
        "id": "EVT-SKIP",
        "resource": {"id": "SUB-SKIP", "status": "ACTIVE"},
    }).encode()
    result = await p.verify_webhook(headers={}, raw_body=body)
    assert result.verified is True
    assert result.event_type == "BILLING.SUBSCRIPTION.ACTIVATED"


@pytest.mark.asyncio
async def test_verify_webhook_no_webhook_id_returns_unverified() -> None:
    p = PayPalProvider(client_id="id", client_secret="secret", webhook_id="", skip_verify=False)
    body = json.dumps({
        "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
        "id": "EVT-NOWH",
        "resource": {"id": "SUB-NOWH"},
    }).encode()
    result = await p.verify_webhook(headers={}, raw_body=body)
    assert result.verified is False


# ---------------------------------------------------------------------------
# NEW: plan missing external_paypal_plan_id → 422
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkout_422_when_plan_missing_paypal_id(
    client: AsyncClient, fresh_engine: Any
) -> None:
    """Paid plan with no external_paypal_plan_id must return 422, not call PayPal."""
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        # Plans seeded WITHOUT paypal plan IDs
        await _seed_plans(s, with_paypal_plan_id=False)

    token = await _register_login(client, VALID_USER)
    provider = _mock_provider(configured=True)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/checkout/paypal",
            json={"plan_code": "pro"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 422
    assert "not configured" in r.json()["detail"].lower()
    # Provider's create_subscription must NOT have been called
    provider.create_subscription.assert_not_called()


# ---------------------------------------------------------------------------
# NEW: checkout passes external_paypal_plan_id (not internal plan code) to PayPal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkout_passes_paypal_plan_id_not_code(
    client: AsyncClient, fresh_engine: Any
) -> None:
    """create_subscription must be called with paypal_plan_id=external_paypal_plan_id."""
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s, with_paypal_plan_id=True)

    token = await _register_login(client, VALID_USER)
    provider = _mock_provider(configured=True)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/checkout/paypal",
            json={"plan_code": "pro"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
    call_kwargs = provider.create_subscription.call_args.kwargs
    # Must use the DB field, not the internal code
    assert call_kwargs["paypal_plan_id"] == "P-PRO-FAKE-001"
    assert call_kwargs["plan_code"] == "pro"


# ---------------------------------------------------------------------------
# NEW: checkout return_url and cancel_url use /billing/success and /billing/cancel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkout_return_cancel_urls(client: AsyncClient, fresh_engine: Any) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s, with_paypal_plan_id=True)

    token = await _register_login(client, VALID_USER)
    provider = _mock_provider(configured=True)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/checkout/paypal",
            json={"plan_code": "pro"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert r.status_code == 200
    call_kwargs = provider.create_subscription.call_args.kwargs
    assert call_kwargs["return_url"].endswith("/billing/success")
    assert call_kwargs["cancel_url"].endswith("/billing/cancel")


# ---------------------------------------------------------------------------
# NEW: webhook PAYMENT.FAILED → past_due
# ---------------------------------------------------------------------------

def test_event_to_status_payment_failed() -> None:
    assert PayPalProvider.event_to_subscription_status(
        "BILLING.SUBSCRIPTION.PAYMENT.FAILED"
    ) == "past_due"


@pytest.mark.asyncio
async def test_webhook_payment_failed_sets_past_due(
    client: AsyncClient, fresh_engine: Any
) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        plans = await _seed_plans(s)
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="pp_fail@example.com",
            username="ppfail",
            full_name="Fail User",
            hashed_password="x",
        )
        s.add(user)
        sub = UserSubscription(
            user_id=user_id,
            plan_id=plans["pro"].id,
            status="active",
            external_provider="paypal",
            external_subscription_id="SUB-FAIL-1",
        )
        s.add(sub)
        await s.commit()
        sub_db_id = sub.id

    verify = _verified_result(
        event_type="BILLING.SUBSCRIPTION.PAYMENT.FAILED",
        event_id="EVT-FAIL-1",
        resource_id="SUB-FAIL-1",
    )
    provider = _mock_provider(verify_result=verify)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/webhooks/paypal",
            content=_webhook_body("BILLING.SUBSCRIPTION.PAYMENT.FAILED", "EVT-FAIL-1"),
            headers={"Content-Type": "application/json"},
        )

    assert r.status_code == 200

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        updated = await s.get(UserSubscription, sub_db_id)
    assert updated.status == "past_due"


# ---------------------------------------------------------------------------
# NEW: malformed webhook body returns 400 (not 500)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_malformed_payload_returns_400(
    client: AsyncClient, fresh_engine: Any
) -> None:
    """Non-JSON or truncated bodies must return 400, not an internal server error."""
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    verify = _verified_result(verified=False)
    provider = _mock_provider(verify_result=verify)

    with patch("app.routes.billing.get_paypal_provider", return_value=provider):
        r = await client.post(
            "/api/billing/webhooks/paypal",
            content=b"not-json{{{",
            headers={"Content-Type": "application/json"},
        )

    assert r.status_code == 400
    assert "verification" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# NEW: production mode (skip_verify=False, no webhook_id) rejects webhook
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_production_mode_no_webhook_id_rejects(
    client: AsyncClient, fresh_engine: Any
) -> None:
    """With skip_verify=False and no webhook_id, webhook must be rejected."""
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    p = PayPalProvider(client_id="id", client_secret="secret", webhook_id="", skip_verify=False)
    verify_result = await p.verify_webhook(
        headers={},
        raw_body=_webhook_body(),
    )
    assert verify_result.verified is False


# ---------------------------------------------------------------------------
# NEW: plans API exposes external_paypal_plan_id field
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_plans_api_exposes_paypal_plan_id(
    client: AsyncClient, fresh_engine: Any
) -> None:
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s, with_paypal_plan_id=True)

    token = await _register_login(client, VALID_USER)
    r = await client.get(
        "/api/billing/plans",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 200
    plans = {p["code"]: p for p in r.json()}
    assert plans["pro"]["external_paypal_plan_id"] == "P-PRO-FAKE-001"
    assert plans["free"]["external_paypal_plan_id"] is None
