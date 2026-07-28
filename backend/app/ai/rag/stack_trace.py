"""Deterministic stack-trace fingerprinting and similarity."""

from __future__ import annotations

import hashlib
import re

from app.domain.services.secret_masker import mask_secrets

_LINE_NO = re.compile(r":\d+(?::\d+)?")
_HEX_ADDR = re.compile(r"\b0x[0-9a-fA-F]+\b")
_GENERATED = re.compile(r"\b(?:tmp|temp|gen|generated)[A-Za-z0-9_-]{4,}\b")
_FRAME = re.compile(
    r"(?:at\s+([\w.$/]+)|File \"([^\"]+)\", line \d+|^\s*([\w.]+)\()",
    re.M,
)
_EXCEPTION = re.compile(r"\b([A-Z][\w.]+(?:Error|Exception))\b")


def normalise_stack_trace(text: str) -> str:
    masked, _ = mask_secrets(text or "")
    cleaned = _LINE_NO.sub("", masked)
    cleaned = _HEX_ADDR.sub("<addr>", cleaned)
    cleaned = _GENERATED.sub("<id>", cleaned)
    return " ".join(cleaned.split())


def stack_trace_fingerprint(text: str) -> str | None:
    """Return a stable fingerprint when a stack-like structure is present."""
    if not text:
        return None
    if not (
        "Traceback" in text
        or "Exception" in text
        or re.search(r"\bat\s+[\w.$]+", text)
        or 'File "' in text
    ):
        return None
    normalised = normalise_stack_trace(text)
    frames = []
    for match in _FRAME.finditer(normalised):
        frame = next((g for g in match.groups() if g), None)
        if frame:
            frames.append(frame)
    exceptions = _EXCEPTION.findall(normalised)
    payload = "|".join(exceptions[:3] + frames[:12])
    if not payload:
        return None
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return digest


def stack_trace_similarity(left: str | None, right: str | None) -> float | None:
    """Jaccard similarity over normalised frames/tokens. Null when either missing."""
    if not left or not right:
        return None
    a = set(normalise_stack_trace(left).lower().split())
    b = set(normalise_stack_trace(right).lower().split())
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
