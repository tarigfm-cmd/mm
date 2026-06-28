"""Abstract base class for payment providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class CheckoutResult:
    checkout_url: str
    external_subscription_id: Optional[str]
    status: str  # e.g. "pending_redirect"
    provider: str


@dataclass
class WebhookVerifyResult:
    verified: bool
    event_type: Optional[str]
    external_event_id: Optional[str]
    external_subscription_id: Optional[str]
    resource_status: Optional[str]
    custom_id: Optional[str]  # set by us at subscription creation; used to resolve user
    payload_summary: dict


class PaymentProviderBase(ABC):
    """Contract every payment provider must fulfil."""

    @property
    @abstractmethod
    def provider_code(self) -> str:
        """Short identifier, e.g. 'paypal'."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if the required credentials are present."""

    @abstractmethod
    async def create_subscription(
        self,
        *,
        plan_code: str,
        price_monthly_cents: int,
        currency: str,
        user_id: str,
        return_url: str,
        cancel_url: str,
    ) -> CheckoutResult:
        """Initiate a payment/subscription flow and return an approval URL."""

    @abstractmethod
    async def verify_webhook(
        self,
        headers: dict,
        raw_body: bytes,
    ) -> WebhookVerifyResult:
        """Verify the webhook signature and parse the event."""
