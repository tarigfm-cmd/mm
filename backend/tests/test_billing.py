"""Tests for subscription billing endpoints and entitlement service."""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import SubscriptionPlan, UsageEvent, UserSubscription
from app.models.identity import User
from app.core.security import hash_password
from app.services.entitlements import (
    can_start_training_session,
    count_monthly_usage,
    get_effective_plan,
    record_usage_event,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_USER = {
    "email": "billing_user@example.com",
    "username": "billinguser",
    "password": "BillingPass1!",
    "full_name": "Billing Tester",
}

ADMIN_USER = {
    "email": "billing_admin@example.com",
    "username": "billingadmin",
    "password": "BillingAdmin1!",
    "full_name": "Billing Admin",
}


async def _register_login(client: AsyncClient, user: dict) -> str:
    await client.post("/api/auth/register", json=user)
    r = await client.post(
        "/api/auth/login", json={"email": user["email"], "password": user["password"]}
    )
    return r.json()["access_token"]


async def _seed_plans(session: AsyncSession) -> dict[str, SubscriptionPlan]:
    """Seed the 4 default plans into the test DB. Returns {code: plan}."""
    plans_data = [
        dict(code="free", name="Free", price_monthly_cents=0,
             max_training_sessions_per_month=20,
             max_published_content_access_per_month=100),
        dict(code="pro", name="Pro", price_monthly_cents=1999,
             max_training_sessions_per_month=1000,
             max_published_content_access_per_month=10000,
             allows_osce=True, allows_games=True),
        dict(code="institution", name="Institution", price_monthly_cents=9900,
             max_training_sessions_per_month=100000,
             allows_institution_dashboard=True, allows_osce=True, allows_games=True),
        dict(code="enterprise", name="Enterprise", price_monthly_cents=49900,
             allows_admin_governance=True, allows_bulk_import=True,
             allows_institution_dashboard=True, allows_osce=True, allows_games=True),
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


async def _create_admin_token(client: AsyncClient, engine) -> tuple[str, uuid.UUID]:
    """Register a superuser and return (access_token, user_id)."""
    from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession
    r = await client.post("/api/auth/register", json=ADMIN_USER)
    assert r.status_code == 201, r.text
    user_id = uuid.UUID(r.json()["id"])

    # Promote to superuser directly in DB
    async with _AsyncSession(engine, expire_on_commit=False) as s:
        user = await s.get(User, user_id)
        user.is_superuser = True
        await s.commit()

    login = await client.post(
        "/api/auth/login",
        json={"email": ADMIN_USER["email"], "password": ADMIN_USER["password"]},
    )
    return login.json()["access_token"], user_id


# ---------------------------------------------------------------------------
# GET /api/billing/plans
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_plans_requires_auth(client: AsyncClient):
    r = await client.get("/api/billing/plans")
    assert r.status_code == 403  # HTTPBearer raises 403 when no credentials


@pytest.mark.asyncio
async def test_list_plans_empty_when_not_seeded(client: AsyncClient):
    token = await _register_login(client, VALID_USER)
    r = await client.get("/api/billing/plans", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_plans_returns_all_active_plans(client: AsyncClient, fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    token = await _register_login(client, VALID_USER)
    r = await client.get("/api/billing/plans", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    codes = [p["code"] for p in r.json()]
    assert set(codes) == {"free", "pro", "institution", "enterprise"}


@pytest.mark.asyncio
async def test_list_plans_sorted_by_price(client: AsyncClient, fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    token = await _register_login(client, VALID_USER)
    r = await client.get("/api/billing/plans", headers={"Authorization": f"Bearer {token}"})
    prices = [p["price_monthly_cents"] for p in r.json()]
    assert prices == sorted(prices)


# ---------------------------------------------------------------------------
# GET /api/billing/me/subscription
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_my_subscription_no_plans_returns_500(client: AsyncClient):
    token = await _register_login(client, VALID_USER)
    r = await client.get(
        "/api/billing/me/subscription", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 500


@pytest.mark.asyncio
async def test_get_my_subscription_free_fallback(client: AsyncClient, fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    token = await _register_login(client, VALID_USER)
    r = await client.get(
        "/api/billing/me/subscription", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_free_tier"] is True
    assert body["subscription"] is None
    assert body["plan"]["code"] == "free"


@pytest.mark.asyncio
async def test_get_my_subscription_reflects_assigned_plan(client: AsyncClient, fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        plans = await _seed_plans(s)

    token = await _register_login(client, VALID_USER)
    admin_token, _ = await _create_admin_token(client, fresh_engine)

    # Get user ID
    me_r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me_r.json()["id"]

    # Admin assigns pro plan
    assign_r = await client.post(
        f"/api/billing/admin/users/{user_id}/subscription",
        json={"plan_code": "pro"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert assign_r.status_code == 200

    # User checks their subscription
    r = await client.get(
        "/api/billing/me/subscription", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_free_tier"] is False
    assert body["plan"]["code"] == "pro"


# ---------------------------------------------------------------------------
# GET /api/billing/me/usage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_my_usage_returns_usage_list(client: AsyncClient):
    token = await _register_login(client, VALID_USER)
    r = await client.get(
        "/api/billing/me/usage", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "usage" in body
    assert isinstance(body["usage"], list)
    assert len(body["usage"]) > 0


@pytest.mark.asyncio
async def test_get_my_usage_starts_at_zero(client: AsyncClient):
    token = await _register_login(client, VALID_USER)
    r = await client.get(
        "/api/billing/me/usage", headers={"Authorization": f"Bearer {token}"}
    )
    for item in r.json()["usage"]:
        assert item["count"] == 0


# ---------------------------------------------------------------------------
# POST /api/billing/admin/users/{user_id}/subscription
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_assign_subscription_requires_superuser(client: AsyncClient, fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    token = await _register_login(client, VALID_USER)
    me_r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me_r.json()["id"]

    r = await client.post(
        f"/api/billing/admin/users/{user_id}/subscription",
        json={"plan_code": "pro"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_assign_subscription_assigns_plan(client: AsyncClient, fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    token = await _register_login(client, VALID_USER)
    me_r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me_r.json()["id"]

    admin_token, _ = await _create_admin_token(client, fresh_engine)
    r = await client.post(
        f"/api/billing/admin/users/{user_id}/subscription",
        json={"plan_code": "pro"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["plan"]["code"] == "pro"
    assert r.json()["status"] == "active"


@pytest.mark.asyncio
async def test_admin_assign_subscription_invalid_plan_code(client: AsyncClient, fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    token = await _register_login(client, VALID_USER)
    me_r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me_r.json()["id"]

    admin_token, _ = await _create_admin_token(client, fresh_engine)
    r = await client.post(
        f"/api/billing/admin/users/{user_id}/subscription",
        json={"plan_code": "nonexistent_plan"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_admin_assign_subscription_user_not_found(client: AsyncClient, fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    admin_token, _ = await _create_admin_token(client, fresh_engine)
    fake_id = uuid.uuid4()
    r = await client.post(
        f"/api/billing/admin/users/{fake_id}/subscription",
        json={"plan_code": "pro"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_assign_subscription_cancels_existing(client: AsyncClient, fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)

    token = await _register_login(client, VALID_USER)
    me_r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me_r.json()["id"]
    admin_token, _ = await _create_admin_token(client, fresh_engine)

    headers = {"Authorization": f"Bearer {admin_token}"}
    # Assign pro
    await client.post(
        f"/api/billing/admin/users/{user_id}/subscription",
        json={"plan_code": "pro"},
        headers=headers,
    )
    # Reassign to institution
    r = await client.post(
        f"/api/billing/admin/users/{user_id}/subscription",
        json={"plan_code": "institution"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["plan"]["code"] == "institution"

    # Subscription endpoint should show institution
    sub_r = await client.get(
        "/api/billing/me/subscription", headers={"Authorization": f"Bearer {token}"}
    )
    assert sub_r.json()["plan"]["code"] == "institution"


# ---------------------------------------------------------------------------
# Entitlement service unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_entitlement_count_monthly_usage_zero(fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    user_id = uuid.uuid4()
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        count = await count_monthly_usage(s, user_id, "training_session_started")
    assert count == 0


@pytest.mark.asyncio
async def test_entitlement_can_start_session_no_plans(fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    user_id = uuid.uuid4()
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        allowed, reason = await can_start_training_session(s, user_id, is_superuser=False)
    assert allowed is True
    assert reason == ""


@pytest.mark.asyncio
async def test_entitlement_superuser_bypasses_limit(fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        plans = await _seed_plans(s)
        plan = plans["free"]

        # Create a user
        user = User(
            email="super@test.com",
            username="supertest",
            hashed_password=hash_password("SuperPass1!"),
            is_superuser=True,
            is_active=True,
        )
        s.add(user)
        await s.flush()

        # Assign free plan with limit=20, record 20 events
        sub = UserSubscription(user_id=user.id, plan_id=plan.id, status="active")
        s.add(sub)
        await s.flush()

        for _ in range(20):
            s.add(UsageEvent(user_id=user.id, event_type="training_session_started"))
        await s.commit()

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        # Superuser should bypass
        allowed, _ = await can_start_training_session(s, user.id, is_superuser=True)
        assert allowed is True


@pytest.mark.asyncio
async def test_entitlement_blocked_when_limit_exceeded(fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        plans = await _seed_plans(s)
        plan = plans["free"]  # limit = 20

        user = User(
            email="limited@test.com",
            username="limitedtest",
            hashed_password=hash_password("LimitedPass1!"),
            is_active=True,
        )
        s.add(user)
        await s.flush()

        sub = UserSubscription(user_id=user.id, plan_id=plan.id, status="active")
        s.add(sub)
        await s.flush()

        # Fill up the monthly quota exactly
        for _ in range(20):
            s.add(UsageEvent(user_id=user.id, event_type="training_session_started"))
        await s.commit()

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        allowed, reason = await can_start_training_session(s, user.id, is_superuser=False)
    assert allowed is False
    assert "limit" in reason.lower()


@pytest.mark.asyncio
async def test_entitlement_allowed_when_under_limit(fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        plans = await _seed_plans(s)
        plan = plans["free"]  # limit = 20

        user = User(
            email="under@test.com",
            username="undertest",
            hashed_password=hash_password("UnderPass1!"),
            is_active=True,
        )
        s.add(user)
        await s.flush()

        sub = UserSubscription(user_id=user.id, plan_id=plan.id, status="active")
        s.add(sub)
        await s.flush()

        # Only 5 events — well under the 20 limit
        for _ in range(5):
            s.add(UsageEvent(user_id=user.id, event_type="training_session_started"))
        await s.commit()

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        allowed, reason = await can_start_training_session(s, user.id, is_superuser=False)
    assert allowed is True
    assert reason == ""


@pytest.mark.asyncio
async def test_entitlement_unlimited_plan_always_allowed(fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        plans = await _seed_plans(s)
        enterprise = plans["enterprise"]  # max_training_sessions=None (unlimited)

        user = User(
            email="unlimited@test.com",
            username="unlimitedtest",
            hashed_password=hash_password("UnlimitedPass1!"),
            is_active=True,
        )
        s.add(user)
        await s.flush()

        sub = UserSubscription(user_id=user.id, plan_id=enterprise.id, status="active")
        s.add(sub)
        await s.flush()

        # Record 1000 events — should still be allowed
        for _ in range(100):
            s.add(UsageEvent(user_id=user.id, event_type="training_session_started"))
        await s.commit()

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        allowed, _ = await can_start_training_session(s, user.id, is_superuser=False)
    assert allowed is True


@pytest.mark.asyncio
async def test_record_usage_event_persists(fresh_engine):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        user = User(
            email="events@test.com",
            username="eventtest",
            hashed_password=hash_password("EventPass1!"),
            is_active=True,
        )
        s.add(user)
        await s.flush()

        await record_usage_event(s, user.id, "training_session_started")
        await s.commit()

    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        result = await s.execute(
            select(UsageEvent).where(UsageEvent.user_id == user.id)
        )
        events = result.scalars().all()
    assert len(events) == 1
    assert events[0].event_type == "training_session_started"


@pytest.mark.asyncio
async def test_get_effective_plan_returns_free_by_default(fresh_engine):
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(fresh_engine, expire_on_commit=False) as s:
        await _seed_plans(s)
        user_id = uuid.uuid4()
        plan = await get_effective_plan(s, user_id)
    assert plan is not None
    assert plan.code == "free"
