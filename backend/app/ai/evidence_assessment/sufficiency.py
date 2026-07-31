"""Evidence sufficiency assessment (coverage / authority / diversity / completeness)."""

from __future__ import annotations

from typing import Any

from app.ai.evidence_assessment.authority import authority_score_for_source
from app.ai.evidence_assessment.diversity import diversity_score
from app.ai.evidence_assessment.versions import EVIDENCE_SUFFICIENCY_VERSION
from app.domain.evidence_assessment.enums import (
    EvidenceAssessmentType,
    EvidenceSufficiencyLevel,
)
from app.domain.evidence_assessment.models import (
    EvidenceAssessment,
    EvidenceSufficiencyAssessment,
)
from app.domain.hypothesis_retrieval.enums import HypothesisRetrievalSourceType
from app.domain.hypothesis_retrieval.models import HypothesisRetrievedItem

SUFFICIENCY_WEIGHTS: dict[str, float] = {
    "coverage": 0.20,
    "authority": 0.18,
    "diversity": 0.12,
    "artifact_completeness": 0.14,
    "temporal_completeness": 0.10,
    "graph_completeness": 0.10,
    "documentation_completeness": 0.08,
    "historical_completeness": 0.08,
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _normalize_weights(active: dict[str, float]) -> dict[str, float]:
    total = sum(abs(v) for v in active.values()) or 1.0
    return {k: abs(v) / total for k, v in active.items()}


def _level_for_score(score: float) -> EvidenceSufficiencyLevel:
    if score >= 0.75:
        return EvidenceSufficiencyLevel.HIGH
    if score >= 0.50:
        return EvidenceSufficiencyLevel.MEDIUM
    if score >= 0.25:
        return EvidenceSufficiencyLevel.LOW
    return EvidenceSufficiencyLevel.INSUFFICIENT


class EvidenceSufficiencyAssessor:
    def assess(
        self,
        *,
        hypothesis_id: str,
        assessments: list[EvidenceAssessment],
        items: list[HypothesisRetrievedItem],
        context: dict[str, Any] | None = None,
    ) -> EvidenceSufficiencyAssessment:
        context = context or {}
        warnings: list[str] = []

        usable = [
            a
            for a in assessments
            if a.assessment_type
            not in {EvidenceAssessmentType.UNRELATED, EvidenceAssessmentType.INSUFFICIENT}
        ]
        coverage = _clamp(len(usable) / 5.0) if assessments else 0.0

        if items:
            authorities = [
                authority_score_for_source(
                    source_type=i.source_type.value
                    if hasattr(i.source_type, "value")
                    else str(i.source_type),
                    source_path=i.source_path,
                    source_system=i.source_system,
                )
                for i in items
            ]
            authority = sum(authorities) / len(authorities)
            div = diversity_score(
                source_types=[
                    i.source_type.value if hasattr(i.source_type, "value") else str(i.source_type)
                    for i in items
                ],
                text_hashes=[i.normalized_text_hash for i in items],
                source_paths=[i.source_path for i in items],
            )
        else:
            authority = 0.0
            div = 0.0
            warnings.append("no_retrieved_items")

        source_set = {
            i.source_type.value if hasattr(i.source_type, "value") else str(i.source_type)
            for i in items
        }
        artifact_c = 1.0 if HypothesisRetrievalSourceType.ARTIFACT.value in source_set else 0.0
        temporal_c = 1.0 if HypothesisRetrievalSourceType.TEMPORAL.value in source_set else 0.0
        graph_c = 1.0 if HypothesisRetrievalSourceType.GRAPH.value in source_set else 0.0
        docs_c = (
            1.0
            if (
                HypothesisRetrievalSourceType.DOCUMENTATION.value in source_set
                or HypothesisRetrievalSourceType.STATIC_KNOWLEDGE.value in source_set
            )
            else 0.0
        )
        hist_c = (
            1.0 if HypothesisRetrievalSourceType.HISTORICAL_INCIDENT.value in source_set else 0.0
        )

        # Soften completeness from context availability signals.
        if context.get("missing_artifacts"):
            artifact_c *= 0.5
            warnings.append("missing_artifacts")
        if context.get("temporal_warnings"):
            temporal_c *= 0.7
            warnings.append("temporal_warnings")
        if context.get("graph_warnings") or context.get("graph_consistency_status") in {
            "INCONSISTENT",
            "PARTIAL",
            "UNKNOWN",
        }:
            graph_c *= 0.6
            warnings.append("graph_inconsistency_or_partial")
        open_set = str(context.get("open_set_status") or "").upper()
        if open_set in {"OPEN", "UNKNOWN", "NOVEL"}:
            warnings.append(f"open_set:{open_set}")
            coverage *= 0.85

        components = {
            "coverage": coverage,
            "authority": _clamp(authority),
            "diversity": _clamp(div),
            "artifact_completeness": artifact_c,
            "temporal_completeness": temporal_c,
            "graph_completeness": graph_c,
            "documentation_completeness": docs_c,
            "historical_completeness": hist_c,
        }
        active = {k: SUFFICIENCY_WEIGHTS[k] for k in components}
        norm = _normalize_weights(active)
        score = _clamp(sum(norm[k] * components[k] for k in components))
        level = _level_for_score(score)
        if level == EvidenceSufficiencyLevel.INSUFFICIENT:
            warnings.append("evidence_sufficiency_insufficient")

        return EvidenceSufficiencyAssessment(
            hypothesis_id=hypothesis_id,
            level=level,
            sufficiency_score=score,
            coverage_score=coverage,
            authority_score=_clamp(authority),
            diversity_score=_clamp(div),
            artifact_completeness=artifact_c,
            temporal_completeness=temporal_c,
            graph_completeness=graph_c,
            documentation_completeness=docs_c,
            historical_completeness=hist_c,
            component_scores=components,
            active_weights=norm,
            warnings=warnings,
            assessor_version=EVIDENCE_SUFFICIENCY_VERSION,
        )
