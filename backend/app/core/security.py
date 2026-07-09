"""Security utilities: password hashing, JWT, secret masking."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import Settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Patterns for masking secrets in logs before storage or LLM processing
SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[\w\-./+=]+", re.I), r"\1=***MASKED***"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA***MASKED***"),
    (re.compile(r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*[:=]\s*[\w/+=]+"), "aws_secret_access_key=***MASKED***"),
    (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "ghp_***MASKED***"),
    (re.compile(r"gho_[a-zA-Z0-9]{36}"), "gho_***MASKED***"),
    (re.compile(r"ghs_[a-zA-Z0-9]{36}"), "ghs_***MASKED***"),
    (re.compile(r"ghr_[a-zA-Z0-9]{36}"), "ghr_***MASKED***"),
    (re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----"), "***PRIVATE_KEY_MASKED***"),
    (re.compile(r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*"), "eyJ***JWT_MASKED***"),
]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    subject: str,
    settings: Settings,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {"sub": subject, "exp": expire, "type": "access"}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.app_secret_key, algorithm=settings.algorithm)


def decode_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.app_secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        from app.core.exceptions import AuthenticationError

        raise AuthenticationError("Invalid or expired token") from exc


def mask_secrets(content: str) -> str:
    """Mask sensitive values in log/config content before persistence or LLM calls."""
    masked = content
    for pattern, replacement in SECRET_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked
