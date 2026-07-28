"""Controlled fusion of deterministic and reasoner diagnoses."""

from __future__ import annotations

from app.ai.orchestration.analysis_context import AnalysisContext
from app.ai.orchestration.models import (
    ConfidenceAssessment,
    EvidenceQualityAssessment,
    FusionResult,
    RetrievalQualityAssessment,
)
from app.domain.enums import RiskLevel


class DiagnosisFusionService:
    def fuse(
        self,
        context: AnalysisContext,
        *,
        confidence: ConfidenceAssessment,
        evidence_quality: EvidenceQualityAssessment,
        retrieval_quality: RetrievalQualityAssessment | None,
        risk: RiskLevel,
    ) -> FusionResult:
        baseline = (
            context.classifications[0].category_code
            if context.classifications
            else "unknown_failure"
        )
        reasoner_category = None
        if context.llm_root_cause and isinstance(context.llm_root_cause.get("root_cause"), dict):
            reasoner_category = (
                str(context.llm_root_cause["root_cause"].get("category") or "") or None
            )

        if reasoner_category is None:
            return FusionResult(
                baseline_category=baseline,
                reasoner_category=None,
                selected_category=baseline,
                override_applied=False,
                override_reason="No reasoner category available.",
                supporting_evidence_ids=_evidence_ids(context),
                supporting_document_ids=_doc_ids(context),
            )

        if reasoner_category == baseline:
            return FusionResult(
                baseline_category=baseline,
                reasoner_category=reasoner_category,
                selected_category=baseline,
                override_applied=False,
                override_reason="Deterministic and reasoner categories agree.",
                supporting_evidence_ids=_evidence_ids(context),
                supporting_document_ids=_doc_ids(context),
            )

        unsupported = 0
        if context.llm_root_cause:
            cited = set(context.llm_root_cause.get("supporting_evidence_ids") or [])
            known = {f"evidence-{i}" for i in range(1, len(context.evidence) + 1)}
            unsupported = len(cited - known)

        grounding_ok = bool(context.grounding_valid) and unsupported == 0
        retrieval_ok = (
            retrieval_quality is not None
            and retrieval_quality.retrieval_executed
            and (retrieval_quality.retrieval_quality_score or 0.0) >= 0.55
        )
        reasoner_conf = None
        if context.llm_root_cause and isinstance(context.llm_root_cause.get("root_cause"), dict):
            try:
                reasoner_conf = float(context.llm_root_cause["root_cause"].get("confidence"))
            except (TypeError, ValueError):
                reasoner_conf = None

        can_override = (
            grounding_ok
            and retrieval_ok
            and evidence_quality.evidence_quality_score >= 0.6
            and (reasoner_conf or 0.0) >= 0.85
            and confidence.calibrated_confidence < 0.70
            and risk not in {RiskLevel.HIGH, RiskLevel.CRITICAL}
        )
        if can_override:
            # Apply override to primary classification for persistence.
            if context.classifications:
                context.classifications[0].category_code = reasoner_category
            return FusionResult(
                baseline_category=baseline,
                reasoner_category=reasoner_category,
                selected_category=reasoner_category,
                override_applied=True,
                override_reason=(
                    "Strongly grounded reasoner override with weak baseline confidence."
                ),
                supporting_evidence_ids=_evidence_ids(context),
                supporting_document_ids=_doc_ids(context),
                alternative_categories=[baseline],
            )

        return FusionResult(
            baseline_category=baseline,
            reasoner_category=reasoner_category,
            selected_category=baseline,
            override_applied=False,
            override_reason=(
                "Disagreement retained; deterministic category kept as authoritative."
            ),
            supporting_evidence_ids=_evidence_ids(context),
            supporting_document_ids=_doc_ids(context),
            alternative_categories=[reasoner_category],
        )


def _evidence_ids(context: AnalysisContext) -> list[str]:
    return [f"evidence-{i}" for i in range(1, len(context.evidence) + 1)]


def _doc_ids(context: AnalysisContext) -> list[str]:
    return [str(c.chunk_id) for c in context.retrieved_chunks]
