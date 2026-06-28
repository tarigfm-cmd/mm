"""Pydantic schemas for subscription billing endpoints."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


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

    model_config = {"from_attributes": True}


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
