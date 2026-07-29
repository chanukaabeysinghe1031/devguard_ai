"""Shared Phase 2 cleaning helpers for DevGuard incident JSON."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

# Standalone titles that are almost never useful knowledge.
_SPAM_TITLE = re.compile(
    r"^\s*("
    r"\+1|thanks?!?|thank you!?|same (here|issue)|me too|bump|any update\??|"
    r"please help|help me|hello|hi+|test|testing|asdf|hhh+|xxx+|lol|ok|okay"
    r")\s*$",
    re.IGNORECASE,
)

_NOISE_LINE = re.compile(
    r"^\s*("
    r"\+1|thanks?!?|thank you!?|same (here|issue)|me too|bump|"
    r"subscribed|sent from my (iphone|ipad|android)|"
    r"<!--.*?-->"
    r")\s*$",
    re.IGNORECASE | re.DOTALL,
)

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_NL = re.compile(r"\n{3,}")
_URL_ONLY_LINE = re.compile(r"^\s*https?://\S+\s*$", re.IGNORECASE)

# Signals that the issue is likely a real failure / bug narrative.
_FAILURE_SIGNAL = re.compile(
    r"(?i)\b("
    r"error|failed|failure|failing|crash|panic|exception|traceback|"
    r"denied|forbidden|timeout|timed?\s*out|unable|cannot|can'?t|"
    r"broken|bug|regression|segfault|oom|killed|"
    r"accessdenied|unauthorized|permission|not\s+found|missing|"
    r"imagepull|crashloop|evicted|unhealthy|"
    r"undeclared|undefined|nullpointer|modulenotfound|"
    r"build\s+fail|deploy(ment)?\s+fail|pipeline\s+fail|"
    r"exit\s+code|non[- ]zero|stack\s+trace"
    r")\b"
)

# Strong "not a failure narrative" patterns (still may keep if failure signals exist).
_FEATURE_REQUEST = re.compile(
    r"(?i)^\s*("
    r"feature\s*request|enhancement|proposal|rfc\b|wishlist|"
    r"add\s+support\s+for|please\s+add|it\s+would\s+be\s+nice"
    r")"
)


@dataclass(frozen=True)
class CleanResult:
    kept: bool
    incident: dict[str, Any] | None
    reject_reason: str | None
    content_hash: str | None
    changed: bool


def _strip_emoji_heavy(text: str) -> str:
    """Remove emoji/symbol noise while keeping normal punctuation and code."""
    out: list[str] = []
    for ch in text:
        if unicodedata.category(ch) in {"So", "Sk"}:
            continue
        out.append(ch)
    return "".join(out)


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    cleaned = text.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = _HTML_COMMENT.sub(" ", cleaned)
    cleaned = _strip_emoji_heavy(cleaned)
    lines: list[str] = []
    for line in cleaned.split("\n"):
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if _NOISE_LINE.match(stripped):
            continue
        if _URL_ONLY_LINE.match(stripped):
            # Keep one URL line max later via join; drop pure URL spam lines for now.
            continue
        lines.append(_MULTI_SPACE.sub(" ", stripped))
    cleaned = "\n".join(lines)
    cleaned = _MULTI_NL.sub("\n\n", cleaned).strip()
    return cleaned


def content_hash(title: str, description: str, repository: str | None) -> str:
    payload = f"{(repository or '').lower()}|{title.lower()}|{description.lower()[:800]}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def should_reject(
    *,
    title: str,
    description: str,
    source_pool: str,
) -> str | None:
    if _SPAM_TITLE.match(title or ""):
        return "spam_or_empty_title"
    if len(title) < 8:
        return "title_too_short"
    combined = f"{title}\n{description}".strip()
    if len(combined) < 40:
        return "text_too_short"
    # Closed knowledge pool: require a failure-like signal OR a reasonably long body.
    has_signal = bool(_FAILURE_SIGNAL.search(combined))
    feature_only = bool(_FEATURE_REQUEST.search(title)) and not has_signal
    if feature_only:
        return "feature_request_without_failure_signal"
    if source_pool == "closed" and not has_signal and len(description) < 120:
        return "weak_failure_signal"
    # Open pool: still drop pure spam, but allow symptom-only short bugs with signals.
    if source_pool == "open" and not has_signal and len(description) < 80:
        return "open_issue_weak_signal"
    return None


def clean_incident(
    raw: dict[str, Any],
    *,
    source_pool: str,
    dataset_version: str,
    mask_secrets_fn,
    seen_hashes: set[str],
) -> CleanResult:
    title = normalize_text(str(raw.get("title") or ""))
    description = normalize_text(str(raw.get("description") or ""))

    masked_title, title_hits = mask_secrets_fn(title)
    masked_body, body_hits = mask_secrets_fn(description)
    title = normalize_text(masked_title)
    description = normalize_text(masked_body)
    secret_hits = int(title_hits) + int(body_hits)

    reason = should_reject(title=title, description=description, source_pool=source_pool)
    if reason:
        return CleanResult(False, None, reason, None, False)

    digest = content_hash(title, description, raw.get("repository"))
    if digest in seen_hashes:
        return CleanResult(False, None, "near_duplicate", digest, False)
    seen_hashes.add(digest)

    changed = title != str(raw.get("title") or "").strip() or description != str(
        raw.get("description") or ""
    ).strip()

    incident = dict(raw)
    incident["title"] = title
    incident["description"] = description
    incident["secrets_masked"] = bool(raw.get("secrets_masked")) or secret_hits > 0
    incident["secrets_masked_count"] = int(raw.get("secrets_masked_count") or 0) + secret_hits

    # Heuristic symptoms from title when empty.
    if not incident.get("symptoms"):
        incident["symptoms"] = title

    provenance = dict(incident.get("provenance") or {})
    provenance["modified"] = bool(provenance.get("modified")) or changed
    incident["provenance"] = provenance

    collection = dict(incident.get("collection") or {})
    collection["dataset_version"] = dataset_version
    collection["status"] = "sanitised"
    collection["curation_notes"] = (
        f"phase2_clean; source_pool={source_pool}; content_hash={digest}"
    )
    incident["collection"] = collection

    # Preserve pool marker for later curation/eval splits.
    raw_meta = dict(incident.get("raw_metadata") or {})
    raw_meta["phase2_source_pool"] = source_pool
    raw_meta["phase2_content_hash"] = digest
    incident["raw_metadata"] = raw_meta

    return CleanResult(True, incident, None, digest, changed)
