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
