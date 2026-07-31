"""Deterministic hypothesis ranking (RankingScore ≠ RootCauseConfidence)."""

from __future__ import annotations

from app.ai.evidence_assessment.versions import HYPOTHESIS_RANKING_VERSION
from app.domain.evidence_assessment.models import (
    EvidenceSufficiencyAssessment,
    HypothesisContradictionAssessment,
    HypothesisRankingResult,
    HypothesisRankingScore,
    HypothesisSupportAssessment,
)

# Documented default weights — active-weight normalization applied at score time.
RANKING_WEIGHTS: dict[str, float] = {
    "support_score": 0.28,
    "sufficiency_score": 0.18,
    "authority_score": 0.10,
    "diversity_score": 0.06,
    "retrieval_relevance": 0.10,
    "temporal_completeness": 0.05,
    "graph_completeness": 0.05,
    "documentation_completeness": 0.04,
    "historical_completeness": 0.03,
    "parser_confidence": 0.04,
    "generation_prior": 0.07,
    "contradiction_penalty": -0.22,
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _normalize_active(weights: dict[str, float]) -> dict[str, float]:
    total = sum(abs(v) for v in weights.values()) or 1.0
    return {k: abs(v) / total for k, v in weights.items()}


class HypothesisRankingEngine:
    """Weighted ranking with active-weight normalization. Deterministic for same inputs."""

    def __init__(
        self,
        *,
        weights: dict[str, float] | None = None,
        tie_epsilon: float = 0.02,
    ) -> None:
        self._weights = dict(weights or RANKING_WEIGHTS)
        self._tie_epsilon = float(tie_epsilon)

    def rank(
        self,
        *,
        analysis_id: str,
        organization_id: str,
        hypothesis_ids: list[str],
        hypothesis_keys: dict[str, str],
        support_by_id: dict[str, HypothesisSupportAssessment],
        contradiction_by_id: dict[str, HypothesisContradictionAssessment],
        sufficiency_by_id: dict[str, EvidenceSufficiencyAssessment],
        generation_priors: dict[str, float],
        mean_relevance_by_id: dict[str, float] | None = None,
        parser_confidence_by_id: dict[str, float] | None = None,
    ) -> HypothesisRankingResult:
        mean_relevance_by_id = mean_relevance_by_id or {}
        parser_confidence_by_id = parser_confidence_by_id or {}
        scores: list[HypothesisRankingScore] = []
        warnings: list[str] = []

        for hid in sorted(hypothesis_ids):
            support = support_by_id.get(hid)
            contradict = contradiction_by_id.get(hid)
            sufficiency = sufficiency_by_id.get(hid)
            components: dict[str, float] = {
                "support_score": float(support.support_score) if support else 0.0,
                "sufficiency_score": float(sufficiency.sufficiency_score) if sufficiency else 0.0,
                "authority_score": float(sufficiency.authority_score) if sufficiency else 0.0,
                "diversity_score": float(sufficiency.diversity_score) if sufficiency else 0.0,
                "retrieval_relevance": _clamp(mean_relevance_by_id.get(hid, 0.0)),
                "temporal_completeness": (
                    float(sufficiency.temporal_completeness) if sufficiency else 0.0
                ),
                "graph_completeness": float(sufficiency.graph_completeness) if sufficiency else 0.0,
                "documentation_completeness": (
                    float(sufficiency.documentation_completeness) if sufficiency else 0.0
                ),
                "historical_completeness": (
                    float(sufficiency.historical_completeness) if sufficiency else 0.0
                ),
                "parser_confidence": _clamp(parser_confidence_by_id.get(hid, 0.5)),
                "generation_prior": _clamp(generation_priors.get(hid, 0.0)),
                "contradiction_penalty": (
                    float(contradict.contradiction_penalty) if contradict else 0.0
                ),
            }
            active_cfg = {k: self._weights[k] for k in components if k in self._weights}
            norm = _normalize_active(active_cfg)
            contributions: dict[str, float] = {}
            raw = 0.0
            for key, weight_mag in norm.items():
                value = components[key]
                if key == "contradiction_penalty":
                    contrib = -weight_mag * value
                else:
                    contrib = weight_mag * value
                contributions[key] = contrib
                raw += contrib
            ranking_score = _clamp(raw)
            score_warnings: list[str] = []
            if support and support.warnings:
                score_warnings.extend(support.warnings[:3])
            if contradict and contradict.contradiction_item_count:
                score_warnings.append("has_contradiction_candidates")
            if sufficiency and sufficiency.warnings:
                score_warnings.extend(
                    w for w in sufficiency.warnings if w.startswith("open_set") or "graph" in w
                )
            scores.append(
                HypothesisRankingScore(
                    hypothesis_id=hid,
                    hypothesis_key=hypothesis_keys.get(hid, ""),
                    ranking_score=ranking_score,
                    component_scores=components,
                    active_weights=norm,
                    contribution_by_component=contributions,
                    support_score=components["support_score"],
                    contradiction_penalty=components["contradiction_penalty"],
                    sufficiency_score=components["sufficiency_score"],
                    generation_prior_score=components["generation_prior"],
                    warnings=score_warnings,
                    ranker_version=HYPOTHESIS_RANKING_VERSION,
                )
            )

        # Deterministic sort: score desc, then hypothesis_id asc.
        scores.sort(key=lambda s: (-s.ranking_score, s.hypothesis_id))
        for idx, score in enumerate(scores, start=1):
            score.rank = idx

        if len(scores) >= 2:
            delta = abs(scores[0].ranking_score - scores[1].ranking_score)
            if delta <= self._tie_epsilon:
                warnings.append("top_scores_within_tie_epsilon")

        return HypothesisRankingResult(
            analysis_id=analysis_id,
            organization_id=organization_id,
            scores=scores,
            tie_epsilon=self._tie_epsilon,
            warnings=warnings,
            ranker_version=HYPOTHESIS_RANKING_VERSION,
        )
