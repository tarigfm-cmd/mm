"""Tests for app/core/security.py — password hashing and JWT."""
import time
import uuid

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def test_hash_password_returns_string():
    h = hash_password("SecurePass1!")
    assert isinstance(h, str)
    assert h.startswith("pbkdf2:sha256:")


def test_verify_password_correct():
    pw = "CorrectHorse42!"
    assert verify_password(pw, hash_password(pw)) is True


def test_verify_password_wrong():
    h = hash_password("RightPassword1")
    assert verify_password("WrongPassword1", h) is False


def test_hash_is_unique_per_call():
    pw = "SamePassword9!"
    h1 = hash_password(pw)
    h2 = hash_password(pw)
    assert h1 != h2, "Each hash should use a unique salt."


def test_verify_password_truncated_hash_returns_false():
    assert verify_password("anything", "not-a-valid-hash") is False


# ---------------------------------------------------------------------------
# JWT access tokens
# ---------------------------------------------------------------------------

def test_create_access_token_returns_string():
    token = create_access_token(str(uuid.uuid4()))
    assert isinstance(token, str)
    assert len(token) > 20


def test_decode_access_token_returns_subject():
    subject = str(uuid.uuid4())
    token = create_access_token(subject)
    claims = decode_token(token)
    assert claims["sub"] == subject


def test_access_token_type_claim():
    token = create_access_token("user-123")
    claims = decode_token(token)
    assert claims["type"] == "access"


def test_access_token_has_exp_and_iat():
    token = create_access_token("user-abc")
    claims = decode_token(token)
    assert "exp" in claims
    assert "iat" in claims
    assert claims["exp"] > claims["iat"]


def test_extra_claims_are_included():
    token = create_access_token("user-xyz", extra_claims={"role": "admin", "org": "acme"})
    claims = decode_token(token)
    assert claims["role"] == "admin"
    assert claims["org"] == "acme"


# ---------------------------------------------------------------------------
# JWT refresh tokens
# ---------------------------------------------------------------------------

def test_create_refresh_token_returns_string():
    token = create_refresh_token(str(uuid.uuid4()))
    assert isinstance(token, str)


def test_decode_refresh_token_returns_subject():
    subject = str(uuid.uuid4())
    token = create_refresh_token(subject)
    claims = decode_token(token)
    assert claims["sub"] == subject


def test_refresh_token_type_claim():
    token = create_refresh_token("user-456")
    claims = decode_token(token)
    assert claims["type"] == "refresh"


def test_refresh_token_expires_later_than_access_token():
    subject = str(uuid.uuid4())
    access = decode_token(create_access_token(subject))
    refresh = decode_token(create_refresh_token(subject))
    assert refresh["exp"] > access["exp"]


# ---------------------------------------------------------------------------
# Invalid / expired tokens
# ---------------------------------------------------------------------------

def test_decode_invalid_token_raises_value_error():
    with pytest.raises(ValueError, match="Invalid token"):
        decode_token("this.is.not.valid")


def test_decode_tampered_token_raises_value_error():
    token = create_access_token("user-999")
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(ValueError):
        decode_token(tampered)


def test_decode_expired_token_raises_value_error(monkeypatch):
    """Patch datetime so the token looks expired."""
    import app.core.security as sec
    from datetime import datetime, timezone

    token = create_access_token("user-exp")

    original_now = datetime.now

    def fake_now(tz=None):
        # Return a time far in the future so the token appears expired
        return datetime(2099, 1, 1, tzinfo=timezone.utc)

    monkeypatch.setattr("app.core.security.datetime", type("_dt", (), {
        "now": staticmethod(fake_now),
        "fromtimestamp": staticmethod(datetime.fromtimestamp),
    })())

    with pytest.raises(ValueError, match="expired"):
        decode_token(token)


# ---------------------------------------------------------------------------
# Token hashing
# ---------------------------------------------------------------------------

def test_hash_token_is_deterministic():
    t = "some-opaque-token"
    assert hash_token(t) == hash_token(t)


def test_hash_token_different_inputs():
    assert hash_token("token-a") != hash_token("token-b")


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_security_headers_present_on_health(client):
    response = await client.get("/api/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_security_headers_present_on_error_response(client):
    # 404 on unknown routes should still carry security headers
    response = await client.get("/api/no-such-endpoint-xyz")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"


# ---------------------------------------------------------------------------
# Production secret validation
# ---------------------------------------------------------------------------

def _cfg(**overrides):
    from types import SimpleNamespace
    base = dict(
        debug=False,
        secret_key="a-secure-production-secret-key-at-least-50-chars-xyz",
        jwt_secret_key="a-secure-jwt-production-secret-key-abc123def456",
        expose_reset_token_in_dev=False,
        paypal_skip_webhook_verify=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_startup_check_raises_on_default_secret_key():
    from app.main import _check_production_secrets
    with pytest.raises(RuntimeError, match="Unsafe default secret"):
        _check_production_secrets(_cfg(secret_key="change-me-in-production-min-50-chars-000000000000"))


def test_startup_check_raises_on_default_jwt_key():
    from app.main import _check_production_secrets
    with pytest.raises(RuntimeError, match="Unsafe default secret"):
        _check_production_secrets(_cfg(jwt_secret_key="change-me-jwt-secret-key-min-32-chars-00000000000"))


def test_startup_check_passes_with_custom_keys():
    from app.main import _check_production_secrets
    _check_production_secrets(_cfg())  # should not raise


def test_startup_check_skipped_in_debug_mode():
    from app.main import _check_production_secrets
    _check_production_secrets(_cfg(
        debug=True,
        secret_key="change-me-in-production-min-50-chars-000000000000",
        jwt_secret_key="change-me-jwt-secret-key-min-32-chars-00000000000",
    ))  # debug=True bypasses the check


def test_startup_check_warns_expose_reset_token(caplog):
    import logging
    from app.main import _check_production_secrets
    with caplog.at_level(logging.WARNING, logger="app.main"):
        _check_production_secrets(_cfg(expose_reset_token_in_dev=True))
    assert "EXPOSE_RESET_TOKEN_IN_DEV" in caplog.text


def test_startup_check_warns_skip_webhook_verify(caplog):
    import logging
    from app.main import _check_production_secrets
    with caplog.at_level(logging.WARNING, logger="app.main"):
        _check_production_secrets(_cfg(paypal_skip_webhook_verify=True))
    assert "PAYPAL_SKIP_WEBHOOK_VERIFY" in caplog.text


def test_rate_limiter_disabled_in_test_environment():
    from app.core.limiter import limiter
    # The disable_rate_limiting autouse fixture sets this to False before each test
    assert limiter.enabled is False, "autouse fixture should have disabled the rate limiter"
