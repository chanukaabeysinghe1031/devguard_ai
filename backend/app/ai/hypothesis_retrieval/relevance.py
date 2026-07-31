"""Hypothesis retrieval relevance scoring (not causal confidence)."""

from __future__ import annotations

from app.ai.hypothesis_retrieval.versions import HYPOTHESIS_RETRIEVAL_RELEVANCE_VERSION
from app.domain.hypothesis_retrieval.models import (
    HypothesisRetrievalRelevanceAssessment,
    RetrievalCandidateFeatureVector,
)

# Stable documented default weights. Only active (non-null) components contribute.
DEFAULT_WEIGHTS: dict[str, float] = {
    "vector_similarity": 0.18,
    "lexical_similarity": 0.14,
    "exact_error_match": 0.16,
    "exact_identifier_overlap": 0.18,
    "category_match": 0.08,
    "source_path_match": 0.08,
    "same_aws_action": 0.10,
    "same_workflow": 0.04,
    "same_repository": 0.03,
    "historical_incident_quality": 0.05,
    "official_source_authority": 0.04,
    "provenance_completeness": 0.03,
    "graph_distance": 0.05,
    "validation_warning_penalty": -0.10,
}


class HypothesisRetrievalRelevanceScorer:
    """Score retrieval relevance with active-weight normalization."""

    def __init__(
        self,
        *,
        weights: dict[str, float] | None = None,
        exact_identifier_boost_enabled: bool = False,
        exact_identifier_boost: float = 0.12,
    ) -> None:
        self._weights = dict(weights or DEFAULT_WEIGHTS)
        self._exact_boost_enabled = exact_identifier_boost_enabled
        self._exact_boost = exact_identifier_boost

    def score(
        self,
        *,
        item_id: str,
        features: RetrievalCandidateFeatureVector,
        retrieval_score: float | None = None,
    ) -> HypothesisRetrievalRelevanceAssessment:
        components = features.active_components()
        # Invert graph distance into a proximity-like signal when present.
        if "graph_distance" in components:
            distance = components["graph_distance"]
            components["graph_distance"] = 1.0 / (1.0 + max(0.0, distance))

        active_weights: dict[str, float] = {}
        for key, value in components.items():
            if key not in self._weights:
                continue
            weight = self._weights[key]
            if key == "validation_warning_penalty":
                active_weights[key] = weight
            elif value is not None:
                active_weights[key] = abs(weight)

        weight_sum = sum(abs(w) for w in active_weights.values()) or 1.0
        normalized_weights = {k: abs(v) / weight_sum for k, v in active_weights.items()}

        contributions: dict[str, float] = {}
        raw = 0.0
        for key, weight in normalized_weights.items():
            value = float(components.get(key, 0.0))
            if key == "validation_warning_penalty":
                # Penalty uses signed configured weight after normalization magnitude.
                contrib = -abs(weight) * abs(value)
            else:
                contrib = weight * value
            contributions[key] = contrib
            raw += contrib

        if (
            self._exact_boost_enabled
            and float(components.get("exact_identifier_overlap") or 0.0) > 0.0
        ):
            raw += self._exact_boost
            contributions["exact_identifier_boost"] = self._exact_boost
            normalized_weights["exact_identifier_boost"] = self._exact_boost

        # Blend lightly with adapter retrieval_score when present.
        if retrieval_score is not None:
            raw = (0.85 * raw) + (0.15 * float(retrieval_score))
            contributions["adapter_retrieval_score_blend"] = 0.15 * float(retrieval_score)

        normalized = max(0.0, min(1.0, raw))
        warnings: list[str] = []
        if not components:
            warnings.append("no_active_features")
        limitations = [
            "retrieval_relevance_is_not_causal_support",
            "exact_matches_can_be_misleading",
        ]
        return HypothesisRetrievalRelevanceAssessment(
            item_id=item_id,
            raw_score=raw,
            normalized_score=normalized,
            retrieval_relevance_score=normalized,
            component_values={k: float(v) for k, v in components.items()},
            active_weights=normalized_weights,
            contribution_by_component=contributions,
            scorer_version=HYPOTHESIS_RETRIEVAL_RELEVANCE_VERSION,
            warnings=warnings,
            limitations=limitations,
        )
