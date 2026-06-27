"""
Security utilities: password hashing (PBKDF2-SHA256) and JWT (joserfc/HS256).

Intentionally no passlib, python-jose, or PyJWT — those are broken in this
environment. hashlib.pbkdf2_hmac is stdlib; joserfc is the JWT library.
"""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import OctKey

from app.config import get_settings

# ---------------------------------------------------------------------------
# Password hashing — PBKDF2-SHA256 with 260 000 iterations
# ---------------------------------------------------------------------------
_PBKDF2_ALGO = "sha256"
_PBKDF2_ITERATIONS = 260_000
_PREFIX = f"pbkdf2:{_PBKDF2_ALGO}:{_PBKDF2_ITERATIONS}"


def hash_password(password: str) -> str:
    """Return a salted PBKDF2-SHA256 hash suitable for storage."""
    salt = secrets.token_hex(32)
    dk = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, password.encode(), salt.encode(), _PBKDF2_ITERATIONS)
    return f"{_PREFIX}${salt}${dk.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if *plain_password* matches the stored hash."""
    try:
        prefix, salt, dk_hex = hashed_password.split("$")
        _, algo, iters_str = prefix.split(":")
        dk = hashlib.pbkdf2_hmac(algo, plain_password.encode(), salt.encode(), int(iters_str))
        return secrets.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT — HS256 via joserfc
# ---------------------------------------------------------------------------

def _get_key() -> OctKey:
    settings = get_settings()
    raw = settings.jwt_secret_key.encode()
    # OctKey requires at minimum 32 bytes for HS256; pad/truncate to 64
    padded = raw.ljust(32, b"\x00")[:64]
    k = base64.urlsafe_b64encode(padded).rstrip(b"=").decode()
    return OctKey.import_key({"kty": "oct", "k": k})


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """Create a short-lived HS256 JWT access token."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    claims: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "type": "access",
    }
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode({"alg": "HS256"}, claims, _get_key())


def create_refresh_token(subject: str) -> str:
    """Create a long-lived HS256 JWT refresh token."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    claims: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "type": "refresh",
    }
    return jwt.encode({"alg": "HS256"}, claims, _get_key())


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT. Raises ValueError on failure.

    Returns the claims dict on success.
    """
    try:
        result = jwt.decode(token, _get_key())
        claims = result.claims
        now = int(datetime.now(timezone.utc).timestamp())
        if claims.get("exp", 0) < now:
            raise ValueError("Token has expired.")
        return claims
    except JoseError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc


def hash_token(token: str) -> str:
    """SHA-256 hash of a token string for safe DB storage."""
    return hashlib.sha256(token.encode()).hexdigest()
