"""Deterministic hybrid reranker with explainable score breakdowns."""

from __future__ import annotations

from app.ai.rag.deduplicator import CandidateDeduplicator
from app.ai.rag.diversity import DiverseCandidateSelector
from app.ai.rag.hybrid_scorer import HybridRetrievalScorer
from app.ai.rag.models import DiagnosticQuery, RetrievalCandidate
from app.ai.rag.weight_profiles import HybridWeightProfile


class HybridReranker:
    def __init__(self, profile: HybridWeightProfile) -> None:
        self._profile = profile
        self._scorer = HybridRetrievalScorer(profile)
        self._deduper = CandidateDeduplicator()
        self._selector = DiverseCandidateSelector()

    def rerank(
        self,
        query: DiagnosticQuery,
        candidates: list[RetrievalCandidate],
    ) -> tuple[list[RetrievalCandidate], int, int]:
        """Return (selected, duplicate_count, filtered_count)."""
        for candidate in candidates:
            self._scorer.score(candidate, query)
            candidate.clamp_scores()
            self._annotate_reasons(candidate, query)

        # Primary ordering before dedupe.
        candidates.sort(
            key=lambda c: (
                -(c.hybrid_score or 0.0),
                -(c.error_code_score or 0.0),
                -(c.semantic_score or 0.0),
                -(c.authority_score or 0.0),
                c.candidate_id,
            )
        )
        limited = candidates[: self._profile.max_candidates_before_rerank]
        deduped, duplicate_count = self._deduper.deduplicate(limited)

        filtered = 0
        kept: list[RetrievalCandidate] = []
        for candidate in deduped:
            score = candidate.hybrid_score or 0.0
            semantic = candidate.semantic_score
            exact = candidate.error_code_score
            if score < self._profile.min_candidate_score and not (
                exact is not None and exact >= self._profile.min_exact_match_score
            ):
                filtered += 1
                continue
            if (
                semantic is not None
                and semantic < self._profile.min_semantic_score
                and (exact is None or exact < self._profile.min_exact_match_score)
                and self._profile.name == "embedding_baseline_v1"
            ):
                filtered += 1
                continue
            kept.append(candidate)

        selected = self._selector.select(kept, self._profile)
        # Stable final order.
        selected.sort(
            key=lambda c: (
                -(c.hybrid_score or 0.0),
                -(c.error_code_score or 0.0),
                -(c.semantic_score or 0.0),
                -(c.authority_score or 0.0),
                c.candidate_id,
            )
        )
        return selected, duplicate_count, filtered

    def _annotate_reasons(
        self,
        candidate: RetrievalCandidate,
        query: DiagnosticQuery,
    ) -> None:
        reasons = list(candidate.match_reasons)
        if (candidate.error_code_score or 0) >= 0.8:
            reasons.append("matched exact diagnostic error code")
        if (candidate.category_score or 0) >= 0.7:
            reasons.append("same failure category")
        if (candidate.stage_score or 0) >= 0.7:
            reasons.append("same pipeline stage")
        if (candidate.semantic_score or 0) >= 0.7:
            reasons.append("high semantic similarity")
        if (candidate.authority_score or 0) >= 0.75:
            reasons.append("authoritative source documentation")
        if (candidate.history_quality_score or 0) >= 0.7:
            reasons.append("trusted resolved historical incident")
        if query.technologies and (candidate.technology_score or 0) >= 0.7:
            reasons.append("matching technology")
        # Dedupe reasons while preserving order.
        seen: set[str] = set()
        unique: list[str] = []
        for reason in reasons:
            if reason not in seen:
                seen.add(reason)
                unique.append(reason)
        candidate.match_reasons = unique[:8]
