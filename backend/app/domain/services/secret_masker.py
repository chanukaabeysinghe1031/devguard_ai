"""Secret redaction for uploaded text. Never log plaintext secrets."""

from __future__ import annotations

import re

# Patterns cover common CI/cloud credentials without attempting full DLP.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)(aws_secret_access_key\s*[=:]\s*)([^\s\"']+)"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(?i)(aws_access_key_id\s*[=:]\s*)(AKIA[0-9A-Z]{16})"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"AKIA[0-9A-Z]{16}"),
        "[REDACTED_AWS_KEY]",
    ),
    (
        re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([^\s\"']+)"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(?i)(password\s*[=:]\s*)([^\s\"']+)"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(?i)(secret\s*[=:]\s*)([^\s\"']+)"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(?i)(token\s*[=:]\s*)([^\s\"']+)"),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"ghp_[A-Za-z0-9]{20,}"),
        "[REDACTED_GITHUB_TOKEN]",
    ),
    (
        re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
        "[REDACTED_GITHUB_TOKEN]",
    ),
    (
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
            r"[\s\S]*?"
            r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
)


def mask_secrets(content: str) -> tuple[str, int]:
    """Return (masked_content, replacement_count)."""
    masked = content
    count = 0
    for pattern, replacement in _SECRET_PATTERNS:
        masked, n = pattern.subn(replacement, masked)
        count += n
    return masked, count
