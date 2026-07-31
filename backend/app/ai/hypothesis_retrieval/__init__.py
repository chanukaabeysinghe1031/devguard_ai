"""Phase 6A.5 Part 1B — hypothesis-directed retrieval AI package."""

from app.ai.hypothesis_retrieval.orchestrator import (
    HypothesisDirectedRetrievalOrchestrator,
    is_hypothesis_eligible_for_retrieval,
)
from app.ai.hypothesis_retrieval.persist import HypothesisRetrievalPersistService

__all__ = [
    "HypothesisDirectedRetrievalOrchestrator",
    "HypothesisRetrievalPersistService",
    "is_hypothesis_eligible_for_retrieval",
]
