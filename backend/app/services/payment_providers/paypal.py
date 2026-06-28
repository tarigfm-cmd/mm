"""PayPal payment provider implementation.

Uses the PayPal Subscriptions v1 API for recurring billing.
Credentials are read from Settings at construction time.

If credentials are absent, all methods raise PayPalNotConfiguredError.
The checkout endpoint catches this and returns HTTP 503.

PayPal Sandbox:  https://api-m.sandbox.paypal.com
PayPal Live:     https://api-m.paypal.com

PayPal subscription flow:
  1. POST /v1/billing/subscriptions  -> approval_url in links
  2. User approves at approval_url
  3. PayPal POSTs BILLING.SUBSCRIPTION.ACTIVATED webhook
  4. We activate UserSubscription from the webhook (NOT from the return URL)
"""
import json
import logging
from typing import Optional

import httpx

from app.services.payment_providers.base import (
    CheckoutResult,
    PaymentProviderBase,
    WebhookVerifyResult,
)

logger = logging.getLogger(__name__)

# PayPal subscription status → our internal status
_PAYPAL_STATUS_MAP: dict[str, str] = {
    "ACTIVE": "active",
    "CANCELLED": "canceled",
    "SUSPENDED": "past_due",
    "EXPIRED": "expired",
    "APPROVAL_PENDING": "trialing",
}

# PayPal event type → internal subscription status transition
_EVENT_TO_STATUS: dict[str, str] = {
    "BILLING.SUBSCRIPTION.ACTIVATED": "active",
    "BILLING.SUBSCRIPTION.CANCELLED": "canceled",
    "BILLING.SUBSCRIPTION.SUSPENDED": "past_due",
    "BILLING.SUBSCRIPTION.EXPIRED": "expired",
    "BILLING.SUBSCRIPTION.PAYMENT.FAILED": "past_due",
    # Payment completed events confirm activity; no status change needed
    "PAYMENT.SALE.COMPLETED": "active",
}


class PayPalNotConfiguredError(Exception):
    """Raised when PayPal credentials are absent."""


class PayPalProvider(PaymentProviderBase):
    """PayPal Subscriptions API provider."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        webhook_id: str,
        env: str = "sandbox",
        skip_verify: bool = False,
        brand_name: str = "PharmLearn",
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._webhook_id = webhook_id
        self._skip_verify = skip_verify
        self._brand_name = brand_name
        self._base_url = (
            "https://api-m.sandbox.paypal.com"
            if env != "live"
            else "https://api-m.paypal.com"
        )

    @property
    def provider_code(self) -> str:
        return "paypal"

    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise PayPalNotConfiguredError("PayPal credentials are not configured.")

    async def _get_access_token(self) -> str:
        self._require_configured()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
                headers={"Accept": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    async def create_subscription(
        self,
        *,
        plan_code: str,
        paypal_plan_id: str,
        price_monthly_cents: int,
        currency: str,
        user_id: str,
        return_url: str,
        cancel_url: str,
    ) -> CheckoutResult:
        """Create a PayPal subscription using the given PayPal billing plan ID.

        Args:
            plan_code: Internal plan code (for logging only — not sent to PayPal).
            paypal_plan_id: The PayPal billing plan ID (P-xxxx) from the PayPal dashboard.
            price_monthly_cents: Plan price in cents (for logging/metadata only).
            currency: Currency code (e.g. GBP).
            user_id: Internal user UUID string — stored as custom_id and echoed in webhook.
            return_url: URL PayPal redirects to after approval.
            cancel_url: URL PayPal redirects to if user cancels.
        """
        self._require_configured()

        token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

        payload = {
            "plan_id": paypal_plan_id,
            "custom_id": user_id,
            "application_context": {
                "brand_name": self._brand_name,
                "return_url": return_url,
                "cancel_url": cancel_url,
                "user_action": "SUBSCRIBE_NOW",
                "shipping_preference": "NO_SHIPPING",
            },
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/v1/billing/subscriptions",
                json=payload,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

        sub_id = data.get("id", "")
        approval_url = next(
            (lnk["href"] for lnk in data.get("links", []) if lnk["rel"] == "approve"),
            return_url,
        )
        return CheckoutResult(
            checkout_url=approval_url,
            external_subscription_id=sub_id,
            status="pending_redirect",
            provider="paypal",
        )

    async def verify_webhook(
        self,
        headers: dict,
        raw_body: bytes,
    ) -> WebhookVerifyResult:
        """Verify PayPal webhook signature and parse the event.

        If _skip_verify is True (test/dev mode), skip the API call.
        In production _skip_verify must be False and _webhook_id must be set.
        """
        try:
            body_json = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError):
            return WebhookVerifyResult(
                verified=False,
                event_type=None,
                external_event_id=None,
                external_subscription_id=None,
                resource_status=None,
                custom_id=None,
                payload_summary={},
            )

        event_type: Optional[str] = body_json.get("event_type")
        event_id: Optional[str] = body_json.get("id")
        resource: dict = body_json.get("resource", {})
        resource_id: Optional[str] = resource.get("id")
        resource_status: Optional[str] = resource.get("status")
        custom_id: Optional[str] = resource.get("custom_id")

        payload_summary = {
            "event_type": event_type,
            "event_id": event_id,
            "resource_id": resource_id,
            "resource_status": resource_status,
        }

        if self._skip_verify:
            return WebhookVerifyResult(
                verified=True,
                event_type=event_type,
                external_event_id=event_id,
                external_subscription_id=resource_id,
                resource_status=resource_status,
                custom_id=custom_id,
                payload_summary=payload_summary,
            )

        if not self._webhook_id:
            logger.warning("PAYPAL_WEBHOOK_ID not set; rejecting webhook.")
            return WebhookVerifyResult(
                verified=False,
                event_type=event_type,
                external_event_id=event_id,
                external_subscription_id=resource_id,
                resource_status=resource_status,
                custom_id=custom_id,
                payload_summary=payload_summary,
            )

        try:
            token = await self._get_access_token()
            verify_payload = {
                "auth_algo": headers.get("paypal-auth-algo", ""),
                "cert_url": headers.get("paypal-cert-url", ""),
                "transmission_id": headers.get("paypal-transmission-id", ""),
                "transmission_sig": headers.get("paypal-transmission-sig", ""),
                "transmission_time": headers.get("paypal-transmission-time", ""),
                "webhook_id": self._webhook_id,
                "webhook_event": body_json,
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/v1/notifications/verify-webhook-signature",
                    json=verify_payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                verify_status = resp.json().get("verification_status", "FAILURE")
        except Exception as exc:
            logger.error("PayPal webhook verification failed: %s", exc)
            return WebhookVerifyResult(
                verified=False,
                event_type=event_type,
                external_event_id=event_id,
                external_subscription_id=resource_id,
                resource_status=resource_status,
                custom_id=custom_id,
                payload_summary=payload_summary,
            )

        return WebhookVerifyResult(
            verified=(verify_status == "SUCCESS"),
            event_type=event_type,
            external_event_id=event_id,
            external_subscription_id=resource_id,
            resource_status=resource_status,
            custom_id=custom_id,
            payload_summary=payload_summary,
        )

    @classmethod
    def event_to_subscription_status(cls, event_type: Optional[str]) -> Optional[str]:
        """Map a PayPal event type to an internal subscription status, or None."""
        if event_type is None:
            return None
        return _EVENT_TO_STATUS.get(event_type)
