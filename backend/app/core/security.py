"""Password hashing and JWT helpers. Never log secrets or tokens."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

import bcrypt
import jwt

from app.core.config import Settings

TokenType = Literal["access", "refresh"]

_INSECURE_SECRETS = frozenset(
    {
        "",
        "secret",
        "changeme",
        "change_me",
        "dev-secret",
        "devguard-secret",
        "jwt-secret",
    }
)


class SecurityConfigurationError(RuntimeError):
    """Raised when JWT/password security settings are unsafe."""


def validate_jwt_settings(settings: Settings) -> None:
    """Fail safely when the JWT secret is missing or insecure."""
    secret = (settings.jwt_secret_key or "").strip()
    if not secret:
        raise SecurityConfigurationError("JWT_SECRET_KEY is required.")
    if secret.lower() in _INSECURE_SECRETS:
        raise SecurityConfigurationError("JWT_SECRET_KEY is insecure.")
    if len(secret) < 32:
        raise SecurityConfigurationError("JWT_SECRET_KEY must be at least 32 characters.")
    if settings.is_production and settings.jwt_secret_key.startswith("dev-"):
        raise SecurityConfigurationError("Production JWT_SECRET_KEY must not use a dev prefix.")


def hash_password(password: str) -> str:
    """Hash a password with bcrypt. Never log the plaintext password."""
    if not password:
        raise ValueError("Password must not be empty.")
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against bcrypt or legacy PBKDF2 bootstrap hashes."""
    if not password or not password_hash:
        return False

    if password_hash.startswith("$2"):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except (ValueError, TypeError):
            return False

    # Legacy bootstrap format: pbkdf2_sha256$salt$hex
    if password_hash.startswith("pbkdf2_sha256$"):
        try:
            _, salt, digest_hex = password_hash.split("$", 2)
            expected = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                100_000,
            ).hex()
            return hmac.compare_digest(expected, digest_hex)
        except ValueError:
            return False

    return False


def hash_token(token: str) -> str:
    """Hash a refresh token for at-rest storage (not reversible)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    *,
    subject: UUID,
    settings: Settings,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    validate_jwt_settings(settings)
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expires_in = int(expires_delta.total_seconds())
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + expires_delta,
        "type": "access",
        "jti": str(uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_in


def create_refresh_token(
    *,
    subject: UUID,
    settings: Settings,
) -> tuple[str, str, datetime]:
    """Return (token, jti, expires_at)."""
    validate_jwt_settings(settings)
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    jti = str(uuid4())
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": expires_at,
        "type": "refresh",
        "jti": jti,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def decode_token(
    token: str,
    *,
    settings: Settings,
    expected_type: TokenType,
) -> dict[str, Any]:
    """Decode and validate a JWT. Raises jwt.PyJWTError on failure."""
    validate_jwt_settings(settings)
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        options={"require": ["sub", "exp", "iat", "iss", "type", "jti"]},
    )
    token_type = payload.get("type")
    if token_type != expected_type:
        raise jwt.InvalidTokenError(f"Expected token type '{expected_type}'.")
    return payload


def generate_secure_secret(length: int = 48) -> str:
    """Utility for generating JWT secrets (not used at runtime)."""
    return secrets.token_urlsafe(length)
