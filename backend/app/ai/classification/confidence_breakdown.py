"""Classification confidence decomposition (Phase 6A.3).

Does not alter Module 8 global causal/final confidence — produces a parallel
interpretable breakdown for hierarchical classification only.
"""

from __future__ import annotations

from app.domain.classification.models import (
    ClassificationConfidenceBreakdown,
    ClassificationConfidenceComponent,
    ClassificationDisagreementResult,
    OpenSetAssessment,
    StageClassifierResult,
)

_WEIGHTS: dict[str, float] = {
    "rule_confidence": 0.22,
    "learned_model_confidence": 0.14,
    "llm_classification_confidence": 0.10,
    "taxonomy_mapping_confidence": 0.08,
    "evidence_coverage": 0.10,
    "temporal_support": 0.06,
    "graph_support": 0.06,
    "representation_similarity": 0.06,
    "classifier_agreement": 0.10,
    "open_set_confidence": 0.08,
}


class ClassificationConfidenceDecomposer:
    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled

    def decompose(
        self,
        *,
        rule_result: StageClassifierResult | None,
        learned_result: StageClassifierResult | None,
        llm_result: StageClassifierResult | None,
        taxonomy_mapping_ok: bool,
        evidence_coverage: float,
        temporal_support: float,
        graph_support: float,
        disagreement: ClassificationDisagreementResult | None,
        open_set: OpenSetAssessment | None,
        missing_evidence_count: int = 0,
    ) -> ClassificationConfidenceBreakdown:
        if not self._enabled:
            return ClassificationConfidenceBreakdown(final_confidence=0.0)

        def _norm(value: float) -> float:
            return max(0.0, min(1.0, float(value)))

        raws: dict[str, tuple[float, str, str]] = {
            "rule_confidence": (
                rule_result.confidence if rule_result and rule_result.executed else 0.0,
                "rule_classifier",
                "Deterministic rule match confidence.",
            ),
            "learned_model_confidence": (
                learned_result.confidence if learned_result and learned_result.executed else 0.0,
                "keyword_learned_stage",
                "Keyword/hybrid learned-stage confidence.",
            ),
            "llm_classification_confidence": (
                llm_result.confidence if llm_result and llm_result.executed else 0.0,
                "llm_classifier",
                "Structured LLM classification confidence (validated codes only).",
            ),
            "taxonomy_mapping_confidence": (
                1.0 if taxonomy_mapping_ok else 0.2,
                "taxonomy_registry",
                "Whether the final code maps to an active frozen hierarchy path.",
            ),
            "evidence_coverage": (
                evidence_coverage,
                "evidence",
                "Fraction of useful classification evidence available.",
            ),
            "temporal_support": (
                temporal_support,
                "temporal_localisation",
                "Temporal localisation support for the category.",
            ),
            "graph_support": (
                graph_support,
                "evidence_graph",
                "Evidence-graph support for the category.",
            ),
            "representation_similarity": (
                (
                    learned_result.representation_quality
                    if learned_result and learned_result.representation_quality is not None
                    else (learned_result.confidence if learned_result else 0.0)
                ),
                "representation",
                "Representation / keyword similarity quality.",
            ),
            "classifier_agreement": (
                {
                    "HIGH": 1.0,
                    "MODERATE": 0.7,
                    "LOW": 0.4,
                    "SEVERE": 0.15,
                    "NOT_APPLICABLE": 0.5,
                }.get(
                    disagreement.agreement_level.value if disagreement else "NOT_APPLICABLE",
                    0.5,
                ),
                "disagreement_analyzer",
                "Agreement among classification mechanisms.",
            ),
            "open_set_confidence": (
                {
                    "KNOWN": 1.0,
                    "UNCERTAIN": 0.45,
                    "UNKNOWN": 0.1,
                }.get(open_set.status.value if open_set else "UNCERTAIN", 0.45),
                "open_set_detector",
                "Confidence that the failure belongs to the known taxonomy.",
            ),
        }

        components: list[ClassificationConfidenceComponent] = []
        total = 0.0
        for name, weight in _WEIGHTS.items():
            raw, source, expl = raws[name]
            norm = _norm(raw)
            contrib = round(norm * weight, 4)
            total += contrib
            components.append(
                ClassificationConfidenceComponent(
                    component_name=name,
                    raw_value=round(float(raw), 4),
                    normalized_value=round(norm, 4),
                    weight=weight,
                    contribution=contrib,
                    source=source,
                    explanation=expl,
                )
            )

        contradiction_penalty = float(disagreement.confidence_penalty) if disagreement else 0.0
        missing_penalty = min(0.25, 0.04 * max(0, missing_evidence_count))
        components.append(
            ClassificationConfidenceComponent(
                component_name="contradiction_penalty",
                raw_value=round(contradiction_penalty, 4),
                normalized_value=round(contradiction_penalty, 4),
                weight=-1.0,
                contribution=round(-contradiction_penalty, 4),
                source="disagreement_analyzer",
                explanation="Penalty from classifier/evidence disagreement.",
            )
        )
        components.append(
            ClassificationConfidenceComponent(
                component_name="missing_evidence_penalty",
                raw_value=round(missing_penalty, 4),
                normalized_value=round(missing_penalty, 4),
                weight=-1.0,
                contribution=round(-missing_penalty, 4),
                source="evidence",
                explanation="Penalty for missing artifacts or signals.",
            )
        )
        final = max(0.0, min(1.0, total - contradiction_penalty - missing_penalty))
        return ClassificationConfidenceBreakdown(
            components=components,
            final_confidence=round(final, 4),
        )
