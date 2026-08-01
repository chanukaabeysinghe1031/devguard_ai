"""Hypothesis support analysis from evidence assessments (candidates only)."""

from __future__ import annotations

from app.ai.evidence_assessment.versions import SUPPORT_ANALYSIS_VERSION
from app.domain.evidence_assessment.enums import EvidenceAssessmentType
from app.domain.evidence_assessment.models import (
    EvidenceAssessment,
    HypothesisSupportAssessment,
)

SUPPORT_WEIGHTS: dict[str, float] = {
    "support_candidate_strength": 0.40,
    "authority_weighted_support": 0.25,
    "exact_identifier_overlap": 0.20,
    "relevance_mean": 0.15,
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _normalize_weights(active: dict[str, float]) -> dict[str, float]:
    total = sum(abs(v) for v in active.values()) or 1.0
    return {k: abs(v) / total for k, v in active.items()}


class HypothesisSupportAnalyzer:
    def analyze(
        self,
        *,
        hypothesis_id: str,
        assessments: list[EvidenceAssessment],
    ) -> HypothesisSupportAssessment:
        support_items = [
            a for a in assessments if a.assessment_type == EvidenceAssessmentType.SUPPORT_CANDIDATE
        ]
        warnings: list[str] = []
        if not assessments:
            warnings.append("no_evidence_assessments")
        if not support_items:
            warnings.append("no_support_candidates")

        if support_items:
            strength = sum(a.confidence for a in support_items) / len(support_items)
            authority = sum(a.authority_score * a.confidence for a in support_items) / max(
                sum(a.confidence for a in support_items), 1e-9
            )
            exact = sum(a.exact_identifier_overlap for a in support_items) / len(support_items)
            relevance = sum(a.relevance_score for a in support_items) / len(support_items)
        else:
            strength = authority = exact = relevance = 0.0

        components = {
            "support_candidate_strength": _clamp(strength),
            "authority_weighted_support": _clamp(authority),
            "exact_identifier_overlap": _clamp(exact),
            "relevance_mean": _clamp(relevance),
        }
        # Count bonus: more independent support candidates (capped).
        count_bonus = min(0.15, 0.05 * max(0, len(support_items) - 1))
        active = {k: SUPPORT_WEIGHTS[k] for k in components}
        norm = _normalize_weights(active)
        contributions = {k: norm[k] * components[k] for k in components}
        score = _clamp(sum(contributions.values()) + count_bonus)

        return HypothesisSupportAssessment(
            hypothesis_id=hypothesis_id,
            support_score=score,
            support_item_count=len(support_items),
            support_candidate_ids=sorted(a.item_id for a in support_items),
            component_scores=components,
            active_weights=norm,
            contribution_by_component=contributions,
            warnings=warnings,
            analyzer_version=SUPPORT_ANALYSIS_VERSION,
        )
