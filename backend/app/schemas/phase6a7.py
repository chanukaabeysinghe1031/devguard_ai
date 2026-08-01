"""Phase 6A.7 final diagnosis read API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FinalDiagnosisResponse(BaseModel):
    analysis_run_id: str
    status: str
    selected_hypothesis_id: str | None = None
    selected_remediation_candidate_id: str | None = None
    final_category_code: str | None = None
    final_title: str | None = None
    final_summary: str | None = None
    root_cause_statement: str | None = None
    confidence: float = 0.0
    confidence_band: str | None = None
    verifier_support: str | None = None
    evidence_sufficiency: float = 0.0
    contradiction_penalty: float = 0.0
    top_hypothesis_margin: float = 0.0
    abstention_reason_codes: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    decision_version: str | None = None
    created_at: str | None = None
    disclaimer: str = (
        "Final diagnosis is evidence-based, not mathematical proof. "
        "Verified remediation is not applied remediation. "
        "Highest-ranked hypothesis is not proven root cause."
    )


class FinalConfidenceResponse(BaseModel):
    analysis_run_id: str
    final_confidence: float = 0.0
    confidence_band: str | None = None
    positive_score: float = 0.0
    negative_score: float = 0.0
    components: dict[str, float] = Field(default_factory=dict)
    weights: dict[str, float] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    calculator_version: str | None = None
    disclaimer: str = (
        "Heuristic confidence score — not a calibrated probability unless "
        "calibration experiments exist."
    )


class AbstentionDecisionResponse(BaseModel):
    analysis_run_id: str
    should_abstain: bool = True
    primary_reason: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    explanation: str = ""
    missing_evidence: list[str] = Field(default_factory=list)
    suggested_next_evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    engine_version: str | None = None
    disclaimer: str = "Abstention is intentional safe behavior, not an error."


class FinalExplanationResponse(BaseModel):
    analysis_run_id: str
    sections: dict[str, str] = Field(default_factory=dict)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    verifier_summary: str = ""
    remediation_summary: str = ""
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    builder_version: str | None = None
    disclaimer: str = "Structured summary only. No hidden chain-of-thought, prompts, or secrets."


class FinalVerifierSummaryResponse(BaseModel):
    analysis_run_id: str
    aggregation: dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = (
        "Verifier support reflects temporary-workspace checks only. "
        "UNAVAILABLE never counts as PASS. Not applied remediation."
    )
