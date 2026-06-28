"""Pydantic schemas for subscription billing endpoints."""
import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SubscriptionPlanRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    price_monthly_cents: int
    currency: str
    billing_interval: str
    is_active: bool
    max_training_sessions_per_month: Optional[int]
    max_published_content_access_per_month: Optional[int]
    allows_admin_governance: bool
    allows_bulk_import: bool
    allows_institution_dashboard: bool
    allows_ai_tutor: bool
    allows_osce: bool
    allows_games: bool
    external_paypal_plan_id: Optional[str] = None

    model_config = {"from_attributes": True}


class SubscriptionPlanAdminRead(SubscriptionPlanRead):
    """Extended plan schema for admin endpoints — includes inactive plans."""
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionPlanUpdate(BaseModel):
    """Request body for PATCH /admin/plans/{plan_code}. All fields optional."""
    name: Optional[str] = None
    price_monthly_cents: Optional[int] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None
    external_paypal_plan_id: Optional[str] = Field(None, max_length=100)

    @field_validator("price_monthly_cents")
    @classmethod
    def price_non_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("price_monthly_cents must be >= 0")
        return v

    @field_validator("currency")
    @classmethod
    def currency_uppercase_3(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.fullmatch(r"[A-Z]{3}", v):
            raise ValueError("currency must be an uppercase 3-letter ISO 4217 code (e.g. USD)")
        return v


class UserSubscriptionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    plan_id: uuid.UUID
    status: str
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool
    external_provider: Optional[str]
    created_at: datetime
    updated_at: datetime
    plan: SubscriptionPlanRead

    model_config = {"from_attributes": True}


class UserSubscriptionWithFallback(BaseModel):
    """Subscription info including a free-plan fallback for users with no explicit subscription."""
    subscription: Optional[UserSubscriptionRead]
    plan: SubscriptionPlanRead
    is_free_tier: bool


class UsageSummary(BaseModel):
    event_type: str
    count: int
    limit: Optional[int] = Field(None, description="None means unlimited")
    period: str = "current_month"


class MonthlyUsageResponse(BaseModel):
    usage: list[UsageSummary]
    period_start: datetime


class SubscriptionAssignRequest(BaseModel):
    plan_code: str
    status: str = "active"


class PayPalCheckoutRequest(BaseModel):
    plan_code: str


class PayPalCheckoutResponse(BaseModel):
    checkout_url: str
    external_subscription_id: Optional[str]
    status: str
    provider: str


class PayPalWebhookResponse(BaseModel):
    status: str
    detail: Optional[str] = None


class PaymentWebhookEventRead(BaseModel):
    id: uuid.UUID
    provider: str
    external_event_id: Optional[str]
    event_type: Optional[str]
    processed_status: str
    processing_error: Optional[str]
    received_at: datetime
    processed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class PayPalPlanStatus(BaseModel):
    plan_code: str
    name: str
    is_active: bool
    is_paid: bool
    external_paypal_plan_id_configured: bool
    checkout_ready: bool


class PayPalConfigStatus(BaseModel):
    """Safe PayPal configuration status — never contains secret values."""
    paypal_env: str
    app_public_url: str
    client_id_configured: bool
    client_secret_configured: bool
    webhook_id_configured: bool
    paypal_configured: bool
    webhook_url: str
    success_url: str
    cancel_url: str
    plans: list[PayPalPlanStatus]
    missing_requirements: list[str]
    warnings: list[str]
