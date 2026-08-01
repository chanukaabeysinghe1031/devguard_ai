"""Shared helpers for Part 2 remediation generation."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.ai.counterfactual_remediation.safety import contains_secret_material

_WILDCARD_RE = re.compile(r"(?:\*|:\*|resource\s*=\s*[\"']\*|\bAction\s*[\"']?:\s*[\"']\*|\b\*/\*)")
_ARN_RE = re.compile(r"arn:aws[a-zA-Z0-9\-]*:[^:\s]+:[^:\s]*:\d{12}:[^\s\"']+")
_ACCOUNT_RE = re.compile(r"\b\d{12}\b")
_ORG_SECRET_KEYS = frozenset(
    {
        "secret",
        "password",
        "token",
        "api_key",
        "access_key",
        "private_key",
    }
)


def sha256_text(text: str | None) -> str | None:
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict") and callable(value.to_dict):
        payload = value.to_dict()
        return dict(payload) if isinstance(payload, dict) else {}
    return {}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def first_str(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def contains_wildcard(text: str | None) -> bool:
    if not text:
        return False
    return bool(_WILDCARD_RE.search(text))


def strip_org_specific_identifiers(text: str) -> str:
    """Strip ARNs, account IDs, and secret-like assignments for historical adaptation."""
    cleaned = _ARN_RE.sub("[REDACTED_ARN]", text)
    cleaned = _ACCOUNT_RE.sub("[REDACTED_ACCOUNT]", cleaned)
    cleaned = re.sub(
        r"(?i)(secret|password|token|api[_-]?key)\s*[:=]\s*[^\s\"']+",
        r"\1=[REDACTED]",
        cleaned,
    )
    return cleaned


def looks_like_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in _ORG_SECRET_KEYS)


def safe_replace_once(haystack: str, old: str, new: str) -> str | None:
    """Replace first exact occurrence; return None if old not found or would broaden wildcards."""
    if not old or old not in haystack:
        return None
    if contains_wildcard(new) or contains_secret_material(new):
        return None
    return haystack.replace(old, new, 1)


def current_state_dict(ctx_or_state: Any) -> dict[str, Any]:
    if hasattr(ctx_or_state, "current_state"):
        return as_dict(ctx_or_state.current_state)
    return as_dict(ctx_or_state)


def get_current_values(state: Any) -> dict[str, Any]:
    data = as_dict(state)
    values = data.get("current_values")
    return dict(values) if isinstance(values, dict) else {}


def get_source_fragment(state: Any, fallback: str | None = None) -> str | None:
    data = as_dict(state)
    frag = data.get("source_fragment")
    if isinstance(frag, str) and frag.strip():
        return frag
    return fallback


def flag(settings: Any, name: str, default: bool = False) -> bool:
    if settings is None:
        return default
    if isinstance(settings, dict):
        return bool(settings.get(name, default))
    return bool(getattr(settings, name, default))


def bound_int(settings: Any, name: str, default: int) -> int:
    if settings is None:
        return default
    if isinstance(settings, dict):
        value = settings.get(name, default)
    else:
        value = getattr(settings, name, default)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def bound_float(settings: Any, name: str, default: float) -> float:
    if settings is None:
        return default
    if isinstance(settings, dict):
        value = settings.get(name, default)
    else:
        value = getattr(settings, name, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
