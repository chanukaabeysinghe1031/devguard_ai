"""Deterministic query sanitizer for hypothesis-directed retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.services.secret_masker import mask_secrets

_WS = re.compile(r"\s+")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_URL_CREDS = re.compile(r"(https?://)([^:@/\s]+):([^@/\s]+)@")
_ARN = re.compile(r"arn:aws:[a-z0-9-]+:[a-z0-9-]*:\d{0,12}:[^\s]+", re.IGNORECASE)
_SECRET_LIKE = re.compile(
    r"(AKIA[0-9A-Z]{16})"
    r"|(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
    r"|(password\s*[=:])"
    r"|(secret\s*[=:])"
    r"|(api[_-]?key\s*[=:])",
    re.IGNORECASE,
)


@dataclass(slots=True, frozen=True)
class SanitizedQuery:
    text: str
    normalized: str
    accepted: bool
    rejection_reason: str | None = None


class RetrievalQuerySanitizer:
    """Mask secrets, normalize whitespace/paths, and reject unsafe queries."""

    def __init__(self, *, max_chars: int = 2000) -> None:
        self._max_chars = max(32, max_chars)

    def sanitize(self, text: str | None) -> SanitizedQuery:
        raw = text or ""
        if "\x00" in raw:
            return SanitizedQuery("", "", False, "null_byte")
        cleaned = _CONTROL.sub(" ", raw)
        cleaned = _URL_CREDS.sub(r"\1***:***@", cleaned)
        masked, secret_count = mask_secrets(cleaned)
        if _SECRET_LIKE.search(masked) or secret_count > 0:
            return SanitizedQuery("", "", False, "secret_like")
        # Soft-normalize ARNs: keep structure, collapse whitespace around them.
        masked = _ARN.sub(lambda m: m.group(0).strip(), masked)
        masked = masked.replace("\\", "/")
        normalized = _WS.sub(" ", masked).strip()
        if not normalized:
            return SanitizedQuery("", "", False, "empty")
        if len(normalized) > self._max_chars:
            return SanitizedQuery("", "", False, "oversized")
        return SanitizedQuery(
            text=normalized,
            normalized=normalized.lower(),
            accepted=True,
        )
