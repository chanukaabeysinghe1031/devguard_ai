"""Map retrieved items to EvidenceAssessment (candidates only)."""

from __future__ import annotations

from typing import Any

from app.ai.evidence_assessment.authority import authority_score_for_source
from app.ai.evidence_assessment.versions import EVIDENCE_ASSESSMENT_VERSION
from app.domain.evidence_assessment.enums import EvidenceAssessmentType
from app.domain.evidence_assessment.models import EvidenceAssessment
from app.domain.hypothesis_retrieval.enums import (
    RetrievalItemRelation,
    RetrievalValidationStatus,
)
from app.domain.hypothesis_retrieval.models import HypothesisRetrievedItem


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class EvidenceItemAssessor:
    """Deterministic per-item evidence assessment — never proven/verified."""

    HIGH_RELEVANCE = 0.55
    LOW_RELEVANCE = 0.25
    HIGH_IDENTIFIER = 0.5

    def assess(
        self,
        item: HypothesisRetrievedItem,
        *,
        hypothesis_id: str | None = None,
        validation_status: str | None = None,
    ) -> EvidenceAssessment:
        meta = dict(item.metadata or {})
        relevance = _clamp(
            float(
                meta.get("retrieval_relevance_score", item.retrieval_score)
                if meta.get("retrieval_relevance_score") is not None
                else item.retrieval_score
            )
        )
        features_raw = meta.get("features")
        features: dict[str, Any] = features_raw if isinstance(features_raw, dict) else {}
        exact_id = _clamp(float(features.get("exact_identifier_overlap") or 0.0))
        official = float(features.get("official_source_authority") or 0.0) >= 0.5
        authority = authority_score_for_source(
            source_type=item.source_type.value
            if hasattr(item.source_type, "value")
            else str(item.source_type),
            source_path=item.source_path,
            source_system=item.source_system,
            official_source=official,
        )
        relation = (
            item.relation_candidate.value
            if hasattr(item.relation_candidate, "value")
            else str(item.relation_candidate)
        )
        val_status = validation_status or meta.get("validation_status")
        assessment_type, reasons, warnings = self._classify(
            relation=relation,
            relevance=relevance,
            exact_id=exact_id,
            authority=authority,
            validation_status=str(val_status) if val_status else None,
        )
        confidence = self._confidence(
            assessment_type=assessment_type,
            relevance=relevance,
            authority=authority,
            exact_id=exact_id,
        )
        item_id = item.id or (
            f"{item.query_id}:{item.global_session_order}:{item.normalized_text_hash}"
        )
        return EvidenceAssessment(
            item_id=str(item_id),
            hypothesis_id=hypothesis_id or item.hypothesis_id,
            assessment_type=assessment_type,
            confidence=confidence,
            relevance_score=relevance,
            authority_score=authority,
            exact_identifier_overlap=exact_id,
            source_type=str(
                item.source_type.value
                if hasattr(item.source_type, "value")
                else item.source_type
            ),
            relation_candidate=relation,
            validation_status=str(val_status) if val_status else None,
            reasons=reasons,
            warnings=warnings,
            limitations=[
                "assessment_type_is_candidate_label_only",
                "candidate_label_not_causal_truth_value",
            ],
            assessor_version=EVIDENCE_ASSESSMENT_VERSION,
            metadata={"adapter_name": item.adapter_name},
        )

    def assess_many(
        self,
        items: list[HypothesisRetrievedItem],
        *,
        hypothesis_id: str,
        max_assessments: int = 40,
        validation_by_item: dict[str, str] | None = None,
    ) -> list[EvidenceAssessment]:
        validation_by_item = validation_by_item or {}
        ordered = sorted(
            items,
            key=lambda i: (
                -float(
                    (i.metadata or {}).get("retrieval_relevance_score", i.retrieval_score) or 0.0
                ),
                i.global_session_order,
                i.query_id,
            ),
        )
        results: list[EvidenceAssessment] = []
        for item in ordered[: max(0, max_assessments)]:
            key = item.id or item.normalized_text_hash or ""
            results.append(
                self.assess(
                    item,
                    hypothesis_id=hypothesis_id,
                    validation_status=validation_by_item.get(str(key)),
                )
            )
        return results

    def _classify(
        self,
        *,
        relation: str,
        relevance: float,
        exact_id: float,
        authority: float,
        validation_status: str | None,
    ) -> tuple[EvidenceAssessmentType, list[str], list[str]]:
        reasons: list[str] = []
        warnings: list[str] = []

        if validation_status and validation_status.startswith("REJECTED"):
            return (
                EvidenceAssessmentType.INSUFFICIENT,
                ["rejected_by_validation"],
                [f"validation:{validation_status}"],
            )
        if validation_status == RetrievalValidationStatus.ACCEPTED_WITH_WARNINGS.value:
            warnings.append("accepted_with_validation_warnings")

        if relevance < self.LOW_RELEVANCE and exact_id < 0.15:
            return (
                EvidenceAssessmentType.UNRELATED
                if relevance < 0.12
                else EvidenceAssessmentType.INSUFFICIENT,
                ["low_relevance"],
                warnings,
            )

        support_signal = relation == RetrievalItemRelation.SUPPORT_CANDIDATE.value
        contradict_signal = relation == RetrievalItemRelation.CONTRADICTION_CANDIDATE.value
        context_signal = relation == RetrievalItemRelation.CONTEXT.value

        if support_signal and contradict_signal:
            # Defensive — relation is a single enum; keep AMBIGUOUS path for metadata conflicts.
            return EvidenceAssessmentType.AMBIGUOUS, ["conflicting_relation_signals"], warnings

        if support_signal and relevance >= self.HIGH_RELEVANCE:
            reasons.append("support_candidate_relation")
            reasons.append("high_relevance")
            if exact_id >= self.HIGH_IDENTIFIER:
                reasons.append("exact_identifier_overlap")
            return EvidenceAssessmentType.SUPPORT_CANDIDATE, reasons, warnings

        if support_signal and relevance >= self.LOW_RELEVANCE:
            reasons.append("support_candidate_relation")
            if authority >= 0.7:
                reasons.append("high_authority_source")
            return EvidenceAssessmentType.SUPPORT_CANDIDATE, reasons, warnings

        if contradict_signal and relevance >= self.LOW_RELEVANCE:
            reasons.append("contradiction_candidate_relation")
            if exact_id >= self.HIGH_IDENTIFIER:
                reasons.append("exact_identifier_overlap")
            return EvidenceAssessmentType.CONTRADICTION_CANDIDATE, reasons, warnings

        if context_signal:
            reasons.append("context_relation")
            return EvidenceAssessmentType.CONTEXT_ONLY, reasons, warnings

        if support_signal and relevance < self.LOW_RELEVANCE:
            return (
                EvidenceAssessmentType.AMBIGUOUS,
                ["support_relation_but_weak_relevance"],
                warnings,
            )

        if contradict_signal and relevance < self.LOW_RELEVANCE:
            return (
                EvidenceAssessmentType.AMBIGUOUS,
                ["contradiction_relation_but_weak_relevance"],
                warnings,
            )

        if relevance >= self.HIGH_RELEVANCE and exact_id >= self.HIGH_IDENTIFIER:
            reasons.append("strong_relevance_without_relation")
            return EvidenceAssessmentType.CONTEXT_ONLY, reasons, warnings

        if relevance < self.LOW_RELEVANCE:
            return EvidenceAssessmentType.INSUFFICIENT, ["weak_relevance"], warnings

        return EvidenceAssessmentType.UNRELATED, ["unknown_relation_weak_link"], warnings

    def _confidence(
        self,
        *,
        assessment_type: EvidenceAssessmentType,
        relevance: float,
        authority: float,
        exact_id: float,
    ) -> float:
        base = 0.45 * relevance + 0.30 * authority + 0.25 * exact_id
        if assessment_type in {
            EvidenceAssessmentType.INSUFFICIENT,
            EvidenceAssessmentType.UNRELATED,
        }:
            base *= 0.6
        elif assessment_type == EvidenceAssessmentType.AMBIGUOUS:
            base *= 0.7
        return _clamp(base)
