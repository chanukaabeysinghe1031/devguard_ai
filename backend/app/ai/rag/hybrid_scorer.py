"""Deterministic hybrid retrieval scorer with active-weight normalisation."""

from __future__ import annotations

from app.ai.orchestration.models import clamp01
from app.ai.rag.models import DiagnosticQuery, HybridScoreBreakdown, RetrievalCandidate
from app.ai.rag.weight_profiles import HybridWeightProfile


class HybridRetrievalScorer:
    """Configuration-driven hybrid scorer. Weights are heuristic — tune experimentally."""

    def __init__(self, profile: HybridWeightProfile) -> None:
        self._profile = profile

    @property
    def profile(self) -> HybridWeightProfile:
        return self._profile

    def score(
        self,
        candidate: RetrievalCandidate,
        query: DiagnosticQuery,
        *,
        is_duplicate: bool = False,
    ) -> HybridScoreBreakdown:
        weights: dict[str, float] = {
            "semantic": self._profile.semantic_weight,
            "keyword": self._profile.keyword_weight,
            "error_code": self._profile.error_code_weight,
            "category": self._profile.category_weight,
            "stage": self._profile.stage_weight,
            "technology": self._profile.technology_weight,
            "stack_trace": self._profile.stack_trace_weight,
            "resource": self._profile.resource_weight,
            "authority": self._profile.authority_weight,
            "recency": self._profile.recency_weight,
            "history_quality": self._profile.history_quality_weight,
        }
        scores: dict[str, float | None] = {
            "semantic": candidate.semantic_score,
            "keyword": candidate.keyword_score,
            "error_code": candidate.error_code_score,
            "category": candidate.category_score,
            "stage": candidate.stage_score,
            "technology": candidate.technology_score,
            "stack_trace": candidate.stack_trace_score,
            "resource": candidate.resource_score,
            "authority": candidate.authority_score,
            "recency": candidate.recency_score,
            "history_quality": candidate.history_quality_score,
        }

        active_weight = 0.0
        weighted = 0.0
        for key, weight in weights.items():
            if weight <= 0:
                continue
            value = scores[key]
            if value is None:
                continue  # missing optional metadata is not treated as zero evidence
            active_weight += weight
            weighted += weight * float(value)

        base = (weighted / active_weight) if active_weight > 0 else 0.0

        penalties: dict[str, float] = {}
        if is_duplicate:
            penalties["duplicate"] = self._profile.duplicate_penalty
        meta_cats = {
            str(c).lower() for c in (candidate.metadata.get("failure_categories") or []) if c
        }
        if (
            query.failure_category
            and meta_cats
            and query.failure_category.lower() not in meta_cats
            and query.failure_category.replace("_", " ").lower() not in " ".join(meta_cats)
        ):
            penalties["category_mismatch"] = self._profile.category_mismatch_penalty
        meta_tech = {str(t).lower() for t in (candidate.metadata.get("technologies") or []) if t}
        query_tech = {t.lower() for t in query.technologies}
        if query_tech and meta_tech and query_tech.isdisjoint(meta_tech):
            penalties["technology_mismatch"] = self._profile.technology_mismatch_penalty

        final = clamp01(base - sum(penalties.values()))
        breakdown = HybridScoreBreakdown(
            semantic=candidate.semantic_score,
            keyword=candidate.keyword_score,
            category=candidate.category_score,
            stage=candidate.stage_score,
            technology=candidate.technology_score,
            error_code=candidate.error_code_score,
            stack_trace=candidate.stack_trace_score,
            resource=candidate.resource_score,
            authority=candidate.authority_score,
            recency=candidate.recency_score,
            history_quality=candidate.history_quality_score,
            penalties=penalties,
            final_score=round(final, 6),
            weight_profile=self._profile.name,
        )
        candidate.hybrid_score = breakdown.final_score
        candidate.score_breakdown = breakdown
        return breakdown
