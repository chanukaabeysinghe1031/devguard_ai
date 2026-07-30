"""Symmetric encryption for integration setup state (ADR-005 §6).

Only short-lived, non-credential payloads (the OAuth-style setup ``state``) are
encrypted here. GitHub App private keys, webhook secrets, and installation
access tokens are never persisted.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from cryptography.fernet import Fernet, InvalidToken
from fastapi import status

from app.core.config import Settings
from app.core.exceptions import DevGuardError

logger = structlog.get_logger(__name__)


class IntegrationCryptoError(DevGuardError):
    """Raised when integration state cannot be encrypted or decrypted."""

    def __init__(self, message: str = "Integration state could not be processed.") -> None:
        super().__init__(
            message=message,
            error_code="INTEGRATION_STATE_INVALID",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class IntegrationCryptoConfigurationError(DevGuardError):
    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            error_code="INTEGRATION_ENCRYPTION_MISCONFIGURED",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def _normalise_key(raw: str) -> bytes:
    """Accept a Fernet key directly, or derive one from arbitrary key material."""
    candidate = raw.strip().encode("utf-8")
    try:
        if len(base64.urlsafe_b64decode(candidate)) == 32:
            return candidate
    except (ValueError, TypeError):
        pass
    return base64.urlsafe_b64encode(hashlib.sha256(candidate).digest())


def resolve_fernet_key(settings: Settings) -> bytes:
    """Resolve the integration encryption key.

    Falls back to a key derived from ``JWT_SECRET_KEY`` in development only, so
    local setup does not require an extra secret. Production must configure
    ``INTEGRATION_ENCRYPTION_KEY`` explicitly.
    """
    configured = (settings.integration_encryption_key or "").strip()
    if configured:
        return _normalise_key(configured)

    if settings.is_production:
        raise IntegrationCryptoConfigurationError(
            "INTEGRATION_ENCRYPTION_KEY must be configured in production."
        )
    if not settings.jwt_secret_key:
        raise IntegrationCryptoConfigurationError(
            "INTEGRATION_ENCRYPTION_KEY is not configured and no fallback key material exists."
        )
    logger.warning(
        "integration_encryption_key_derived",
        reason="INTEGRATION_ENCRYPTION_KEY not set; deriving development key from JWT secret",
        environment=settings.environment,
    )
    return _normalise_key(f"devguard-integration:{settings.jwt_secret_key}")


def encrypt_state(payload: dict[str, Any], *, settings: Settings) -> str:
    """Encrypt a JSON-serialisable setup state payload."""
    fernet = Fernet(resolve_fernet_key(settings))
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return fernet.encrypt(raw).decode("ascii")


def decrypt_state(token: str, *, settings: Settings, max_age_seconds: int | None = None) -> dict:
    """Decrypt a setup state token, enforcing both Fernet and payload expiry."""
    fernet = Fernet(resolve_fernet_key(settings))
    try:
        raw = fernet.decrypt(token.encode("ascii"), ttl=max_age_seconds)
    except (InvalidToken, ValueError, UnicodeEncodeError) as exc:
        raise IntegrationCryptoError("Setup state is invalid or has expired.") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise IntegrationCryptoError("Setup state payload is malformed.") from exc
    if not isinstance(payload, dict):
        raise IntegrationCryptoError("Setup state payload is malformed.")

    expires_at = payload.get("expires_at")
    if isinstance(expires_at, str):
        try:
            deadline = datetime.fromisoformat(expires_at)
        except ValueError as exc:
            raise IntegrationCryptoError("Setup state payload is malformed.") from exc
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=UTC)
        if deadline < datetime.now(UTC):
            raise IntegrationCryptoError("Setup state has expired.")
    return payload


def state_expiry(*, ttl_seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=ttl_seconds)).isoformat()
