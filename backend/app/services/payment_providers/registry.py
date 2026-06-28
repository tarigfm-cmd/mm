"""Payment provider registry — constructs providers from Settings."""
from functools import lru_cache

from app.config import get_settings
from app.services.payment_providers.paypal import PayPalProvider


@lru_cache(maxsize=1)
def get_paypal_provider() -> PayPalProvider:
    s = get_settings()
    return PayPalProvider(
        client_id=s.paypal_client_id,
        client_secret=s.paypal_client_secret,
        webhook_id=s.paypal_webhook_id,
        env=s.paypal_env,
        skip_verify=s.paypal_skip_webhook_verify,
    )
