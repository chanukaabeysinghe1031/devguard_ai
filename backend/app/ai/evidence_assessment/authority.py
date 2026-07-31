"""Source authority weights for evidence assessment."""

from __future__ import annotations

from app.domain.hypothesis_retrieval.enums import HypothesisRetrievalSourceType

# Authority order (highest → lowest):
# repository artifact / workflow / terraform / execution log
# > official documentation
# > historical
# > generic semantic

AUTHORITY_BY_SOURCE_TYPE: dict[str, float] = {
    HypothesisRetrievalSourceType.ARTIFACT.value: 1.0,
    HypothesisRetrievalSourceType.REPOSITORY_CHANGE.value: 0.95,
    HypothesisRetrievalSourceType.TEMPORAL.value: 0.90,
    HypothesisRetrievalSourceType.GRAPH.value: 0.88,
    HypothesisRetrievalSourceType.DOCUMENTATION.value: 0.75,
    HypothesisRetrievalSourceType.STATIC_KNOWLEDGE.value: 0.72,
    HypothesisRetrievalSourceType.HISTORICAL_INCIDENT.value: 0.55,
    HypothesisRetrievalSourceType.LEXICAL_KNOWLEDGE.value: 0.40,
    HypothesisRetrievalSourceType.VECTOR_KNOWLEDGE.value: 0.35,
    HypothesisRetrievalSourceType.CLASSIFICATION.value: 0.30,
}

# Path / system heuristics boost within artifact-like sources.
PATH_AUTHORITY_BOOSTS: list[tuple[str, float]] = [
    (".github/workflows/", 0.08),
    ("workflow", 0.06),
    (".tf", 0.08),
    ("terraform", 0.07),
    ("iam", 0.06),
    ("policy", 0.04),
    (".log", 0.05),
    ("actions/runs", 0.05),
]


def authority_score_for_source(
    *,
    source_type: str,
    source_path: str | None = None,
    source_system: str | None = None,
    official_source: bool = False,
) -> float:
    """Return authority in [0, 1] for a retrieved evidence item."""
    base = float(AUTHORITY_BY_SOURCE_TYPE.get(source_type, 0.25))
    path = (source_path or "").lower()
    system = (source_system or "").lower()
    boost = 0.0
    for needle, value in PATH_AUTHORITY_BOOSTS:
        if needle in path or needle in system:
            boost = max(boost, value)
    if official_source or "official" in system or "docs." in path:
        base = max(base, 0.75)
        boost = max(boost, 0.05)
    return max(0.0, min(1.0, base + boost))


def authority_rank(source_type: str) -> int:
    """Lower rank number = higher authority (for deterministic ordering)."""
    order = [
        HypothesisRetrievalSourceType.ARTIFACT.value,
        HypothesisRetrievalSourceType.REPOSITORY_CHANGE.value,
        HypothesisRetrievalSourceType.TEMPORAL.value,
        HypothesisRetrievalSourceType.GRAPH.value,
        HypothesisRetrievalSourceType.DOCUMENTATION.value,
        HypothesisRetrievalSourceType.STATIC_KNOWLEDGE.value,
        HypothesisRetrievalSourceType.HISTORICAL_INCIDENT.value,
        HypothesisRetrievalSourceType.LEXICAL_KNOWLEDGE.value,
        HypothesisRetrievalSourceType.VECTOR_KNOWLEDGE.value,
        HypothesisRetrievalSourceType.CLASSIFICATION.value,
    ]
    try:
        return order.index(source_type)
    except ValueError:
        return len(order)
