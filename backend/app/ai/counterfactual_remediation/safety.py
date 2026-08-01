"""Secret scanning, masking, and untrusted-instruction sanitization for Part 1."""

from __future__ import annotations

import re

from app.domain.services.secret_masker import mask_secrets

# Extra patterns beyond domain secret_masker (Terraform sensitive markers, etc.).
_EXTRA_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*[^\s\"']+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    re.compile(
        r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)"
        r"://[^/\s:@]+:[^@/\s]+@"
    ),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)(password|passwd|pwd)\s*[=:]\s*[^\s\"']+"),
    re.compile(r"(?i)sensitive\s*=\s*true"),
    re.compile(r"(?i)nonsensitive\s*\("),
    re.compile(r"(?i)(aws_access_key_id|secret_access_key)\s*[=:]\s*[^\s\"']+"),
)

_INJECTION_PHRASES: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bignore\s+(all\s+)?previous\s+(instructions?|rules?)\b"),
    re.compile(r"(?i)\bdisregard\s+(all\s+)?(previous|prior)\s+(instructions?|rules?)\b"),
    re.compile(r"(?i)\bdisable\s+(all\s+)?constraints?\b"),
    re.compile(r"(?i)\boverride\s+system\s+rules?\b"),
    re.compile(r"(?i)\bgrant\s+admin\b"),
    re.compile(r"(?i)\bincrease\s+permissions?\b"),
    re.compile(r"(?i)\bexecute\s+(shell|command|terraform\s+apply)\b"),
    re.compile(r"(?i)\bdisclose\s+(secrets?|credentials?|keys?)\b"),
    re.compile(r"(?i)\bchange\s+organization\s+scope\b"),
    re.compile(r"(?i)\byou\s+are\s+now\s+(unrestricted|jailbroken)\b"),
)

_INJECTION_REPLACEMENT = "[UNTRUSTED_INSTRUCTION_IGNORED]"


def mask_for_context(text: str | None) -> str:
    """Mask secrets for context/fragments. Never returns None."""
    if not text:
        return ""
    masked, _ = mask_secrets(text)
    # Soft-mask Terraform sensitive markers without dropping structure.
    masked = re.sub(
        r"(?i)(sensitive\s*=\s*)true",
        r"\1[SENSITIVE]",
        masked,
    )
    return masked


def contains_secret_material(text: str | None) -> bool:
    """True when text appears to contain secret or credential material."""
    if not text:
        return False
    masked, count = mask_secrets(text)
    if count > 0:
        return True
    if masked != text:
        return True
    for pattern in _EXTRA_SECRET_PATTERNS:
        if pattern.search(text):
            return True
    return False


def sanitize_untrusted_instructions(text: str | None) -> str:
    """Strip/ignore prompt-injection style phrases from untrusted artifact text."""
    if not text:
        return ""
    sanitized = text
    for pattern in _INJECTION_PHRASES:
        sanitized = pattern.sub(_INJECTION_REPLACEMENT, sanitized)
    return sanitize_keep_structure(sanitized)


def sanitize_keep_structure(text: str) -> str:
    """Mask secrets after injection sanitization."""
    return mask_for_context(text)
