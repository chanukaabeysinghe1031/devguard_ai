"""Source-authority scoring from chunk metadata."""

from __future__ import annotations

from app.ai.orchestration.models import clamp01
from app.ai.rag.models import RetrievalSourceType

_AUTHORITY: dict[str, float] = {
    "verified_internal_runbook": 0.95,
    "official_vendor_documentation": 0.90,
    "approved_architecture_documentation": 0.85,
    "confirmed_resolved_incident": 0.80,
    "vendor_documentation": 0.78,
    "runbook": 0.75,
    "architecture_document": 0.70,
    "knowledge_document": 0.65,
    "general_internal_note": 0.45,
    "unverified_document": 0.30,
    "internal_resolution": 0.80,
    "historical_incident": 0.80,
}


def authority_score(
    *,
    source_type: RetrievalSourceType | str,
    metadata: dict | None = None,
) -> float:
    meta = metadata or {}
    explicit = str(meta.get("source_authority") or "").lower().strip()
    if explicit in _AUTHORITY:
        return clamp01(_AUTHORITY[explicit])
    key = source_type.value if isinstance(source_type, RetrievalSourceType) else str(source_type)
    if key in _AUTHORITY:
        return clamp01(_AUTHORITY[key])
    provider = str(meta.get("provider") or "").lower()
    if provider in {"aws", "hashicorp", "docker", "github"}:
        return 0.78
    return 0.55
