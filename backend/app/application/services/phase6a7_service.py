"""Read APIs for Phase 6A.7 final diagnosis (no apply / write path)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.application.services.analysis_run_service import AnalysisRunService
from app.core.config import Settings
from app.domain.exceptions.business import ResourceNotFoundError
from app.schemas.phase6a7 import (
    AbstentionDecisionResponse,
    FinalConfidenceResponse,
    FinalDiagnosisResponse,
    FinalExplanationResponse,
    FinalVerifierSummaryResponse,
)


class Phase6A7FinalDiagnosisService:
    def __init__(self, session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._runs = AnalysisRunService(session)

    def _ensure_debug_enabled(self) -> None:
        if not (
            self._settings.final_diagnosis_debug_api_enabled
            or self._settings.final_diagnosis_enabled
        ):
            raise ResourceNotFoundError("Final diagnosis API is not enabled")

    async def _load_payload(self, organization_id: UUID, analysis_run_id: UUID) -> dict[str, Any]:
        self._ensure_debug_enabled()
        run = await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        summary = run.output_summary if isinstance(run.output_summary, dict) else {}
        payload = summary.get("final_diagnosis")
        if not isinstance(payload, dict):
            raise ResourceNotFoundError("Final diagnosis decision not found for analysis")
        return payload

    async def get_final_diagnosis(
        self, *, organization_id: UUID, analysis_run_id: UUID
    ) -> FinalDiagnosisResponse:
        payload = await self._load_payload(organization_id, analysis_run_id)
        return FinalDiagnosisResponse(
            analysis_run_id=str(analysis_run_id),
            status=str(payload.get("status") or "UNKNOWN"),
            selected_hypothesis_id=payload.get("selected_hypothesis_id"),
            selected_remediation_candidate_id=payload.get("selected_remediation_candidate_id"),
            final_category_code=payload.get("final_category_code"),
            final_title=payload.get("final_title"),
            final_summary=payload.get("final_summary"),
            root_cause_statement=payload.get("root_cause_statement"),
            confidence=float(payload.get("confidence") or 0.0),
            confidence_band=payload.get("confidence_band"),
            verifier_support=payload.get("verifier_support"),
            evidence_sufficiency=float(payload.get("evidence_sufficiency") or 0.0),
            contradiction_penalty=float(payload.get("contradiction_penalty") or 0.0),
            top_hypothesis_margin=float(payload.get("top_hypothesis_margin") or 0.0),
            abstention_reason_codes=list(payload.get("abstention_reason_codes") or []),
            missing_evidence=list(payload.get("missing_evidence") or []),
            warnings=list(payload.get("warnings") or []),
            limitations=list(payload.get("limitations") or []),
            decision_version=payload.get("decision_version"),
            created_at=payload.get("created_at"),
        )

    async def get_final_confidence(
        self, *, organization_id: UUID, analysis_run_id: UUID
    ) -> FinalConfidenceResponse:
        payload = await self._load_payload(organization_id, analysis_run_id)
        breakdown = payload.get("confidence_breakdown") or {}
        if not isinstance(breakdown, dict):
            breakdown = {}
        return FinalConfidenceResponse(
            analysis_run_id=str(analysis_run_id),
            final_confidence=float(
                breakdown.get("final_confidence") or payload.get("confidence") or 0.0
            ),
            confidence_band=breakdown.get("confidence_band") or payload.get("confidence_band"),
            positive_score=float(breakdown.get("positive_score") or 0.0),
            negative_score=float(breakdown.get("negative_score") or 0.0),
            components=dict(breakdown.get("components") or payload.get("component_scores") or {}),
            weights=dict(breakdown.get("weights") or {}),
            limitations=list(breakdown.get("limitations") or []),
            calculator_version=breakdown.get("calculator_version"),
        )

    async def get_abstention_decision(
        self, *, organization_id: UUID, analysis_run_id: UUID
    ) -> AbstentionDecisionResponse:
        payload = await self._load_payload(organization_id, analysis_run_id)
        abstention = payload.get("abstention") or {}
        if not isinstance(abstention, dict):
            abstention = {}
        return AbstentionDecisionResponse(
            analysis_run_id=str(analysis_run_id),
            should_abstain=bool(abstention.get("should_abstain", True)),
            primary_reason=abstention.get("primary_reason"),
            reason_codes=list(
                abstention.get("reason_codes") or payload.get("abstention_reason_codes") or []
            ),
            explanation=str(abstention.get("explanation") or ""),
            missing_evidence=list(
                abstention.get("missing_evidence") or payload.get("missing_evidence") or []
            ),
            suggested_next_evidence=list(abstention.get("suggested_next_evidence") or []),
            limitations=list(abstention.get("limitations") or []),
            engine_version=abstention.get("engine_version"),
        )

    async def get_final_explanation(
        self, *, organization_id: UUID, analysis_run_id: UUID
    ) -> FinalExplanationResponse:
        payload = await self._load_payload(organization_id, analysis_run_id)
        explanation = payload.get("explanation") or {}
        if not isinstance(explanation, dict):
            explanation = {}
        return FinalExplanationResponse(
            analysis_run_id=str(analysis_run_id),
            sections=dict(explanation.get("sections") or {}),
            supporting_evidence_ids=list(explanation.get("supporting_evidence_ids") or []),
            contradicting_evidence_ids=list(explanation.get("contradicting_evidence_ids") or []),
            missing_evidence=list(explanation.get("missing_evidence") or []),
            verifier_summary=str(explanation.get("verifier_summary") or ""),
            remediation_summary=str(explanation.get("remediation_summary") or ""),
            warnings=list(explanation.get("warnings") or []),
            limitations=list(explanation.get("limitations") or []),
            builder_version=explanation.get("builder_version"),
        )

    async def get_final_verifier_summary(
        self, *, organization_id: UUID, analysis_run_id: UUID
    ) -> FinalVerifierSummaryResponse:
        payload = await self._load_payload(organization_id, analysis_run_id)
        aggregation = payload.get("verifier_aggregation") or {}
        if not isinstance(aggregation, dict):
            aggregation = {}
        return FinalVerifierSummaryResponse(
            analysis_run_id=str(analysis_run_id),
            aggregation=dict(aggregation),
        )
