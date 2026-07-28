"""Retrieval query construction from classification, evidence, and signals."""

from __future__ import annotations

import re

from app.ai.orchestration.analysis_context import AnalysisContext

_TOKEN = re.compile(r"[A-Za-z0-9_.:/-]{3,}")
_STOP = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "have",
    "been",
    "were",
    "when",
    "into",
    "file",
    "line",
    "error",
    "failed",
}


def build_retrieval_query(context: AnalysisContext) -> str:
    """Combine predicted category, evidence keywords, and signals into a retrieval query."""
    parts: list[str] = []
    if context.classifications:
        primary = context.classifications[0]
        parts.append(primary.category_code.replace("_", " "))
        parts.append(primary.root_cause_summary)

    for item in context.evidence[:5]:
        parts.append(item.normalized_excerpt[:240])

    signals = context.signals or {}
    for key in ("provider", "service", "failed_command", "resource", "environment"):
        value = signals.get(key)
        if value:
            parts.append(str(value))

    # Pull high-signal tokens from combined text.
    tokens: list[str] = []
    seen: set[str] = set()
    for match in _TOKEN.finditer(context.combined_text[:4000]):
        token = match.group(0)
        lowered = token.lower()
        if lowered in _STOP or lowered in seen:
            continue
        if any(ch.isupper() for ch in token) or ":" in token or token.startswith("arn:"):
            seen.add(lowered)
            tokens.append(token)
        if len(tokens) >= 12:
            break
    parts.extend(tokens)

    query = " ".join(p.strip() for p in parts if p and p.strip())
    context.retrieval_query = query[:800]
    return context.retrieval_query
