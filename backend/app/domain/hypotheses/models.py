"""Structured domain models for competing causal hypotheses (Phase 6A.4)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.hypotheses.enums import (
    CausalPathValidationStatus,
    CriticDecision,
    HypothesisEvidenceRelation,
    HypothesisGeneratorType,
    HypothesisRunStatus,
    HypothesisStatus,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class HypothesisEvidenceLink:
    evidence_type: str
    relation: HypothesisEvidenceRelation
    explanation: str = ""
    confidence: float = 0.5
    evidence_item_id: str | None = None
    graph_node_id: str | None = None
    graph_edge_id: str | None = None
    artifact_id: str | None = None
    source_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    extraction_method: str = "deterministic"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["relation"] = self.relation.value
        return data


@dataclass(slots=True)
class HypothesisCriticResult:
    decision: CriticDecision
    explanation: str = ""
    contradictions: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    graph_conflicts: list[str] = field(default_factory=list)
    temporal_conflicts: list[str] = field(default_factory=list)
    specificity_warning: str | None = None
    recommended_status: HypothesisStatus = HypothesisStatus.READY_FOR_RANKING
    critic_version: str = "critic_v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "explanation": self.explanation,
            "contradictions": list(self.contradictions),
            "missing_evidence": list(self.missing_evidence),
            "unsupported_claims": list(self.unsupported_claims),
            "graph_conflicts": list(self.graph_conflicts),
            "temporal_conflicts": list(self.temporal_conflicts),
            "specificity_warning": self.specificity_warning,
            "recommended_status": self.recommended_status.value,
            "critic_version": self.critic_version,
        }


@dataclass(slots=True)
class CausalHypothesis:
    hypothesis_key: str
    title: str
    causal_claim: str
    category_code: str | None = None
    level_1_code: str | None = None
    level_2_code: str | None = None
    level_3_code: str | None = None
    root_cause_node_id: str | None = None
    observed_failure_node_id: str | None = None
    affected_artifact_id: str | None = None
    affected_artifact_type: str | None = None
    affected_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    causal_path_node_ids: list[str] = field(default_factory=list)
    causal_path_edge_ids: list[str] = field(default_factory=list)
    evidence_links: list[HypothesisEvidenceLink] = field(default_factory=list)
    expected_observations: list[str] = field(default_factory=list)
    falsifying_observations: list[str] = field(default_factory=list)
    proposed_verification_steps: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    generator_type: HypothesisGeneratorType = HypothesisGeneratorType.RULE
    generator_name: str = "rule_templates"
    generator_version: str = "v1"
    prompt_version: str | None = None
    template_id: str | None = None
    generation_confidence: float = 0.0
    generation_prior_score: float = 0.0
    path_validation_status: CausalPathValidationStatus = (
        CausalPathValidationStatus.NOT_APPLICABLE
    )
    path_validation_warnings: list[str] = field(default_factory=list)
    status: HypothesisStatus = HypothesisStatus.GENERATED
    rank_placeholder: int = 0
    critic: HypothesisCriticResult | None = None
    warnings: list[str] = field(default_factory=list)
    id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "hypothesis_key": self.hypothesis_key,
            "title": self.title,
            "causal_claim": self.causal_claim,
            "category_code": self.category_code,
            "level_1_code": self.level_1_code,
            "level_2_code": self.level_2_code,
            "level_3_code": self.level_3_code,
            "root_cause_node_id": self.root_cause_node_id,
            "observed_failure_node_id": self.observed_failure_node_id,
            "affected_artifact_id": self.affected_artifact_id,
            "affected_artifact_type": self.affected_artifact_type,
            "affected_path": self.affected_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "causal_path_node_ids": list(self.causal_path_node_ids),
            "causal_path_edge_ids": list(self.causal_path_edge_ids),
            "evidence_links": [e.to_dict() for e in self.evidence_links],
            "expected_observations": list(self.expected_observations),
            "falsifying_observations": list(self.falsifying_observations),
            "proposed_verification_steps": list(self.proposed_verification_steps),
            "limitations": list(self.limitations),
            "missing_evidence": list(self.missing_evidence),
            "generator_type": self.generator_type.value,
            "generator_name": self.generator_name,
            "generator_version": self.generator_version,
            "prompt_version": self.prompt_version,
            "template_id": self.template_id,
            "generation_confidence": self.generation_confidence,
            "generation_prior_score": self.generation_prior_score,
            "path_validation_status": self.path_validation_status.value,
            "path_validation_warnings": list(self.path_validation_warnings),
            "status": self.status.value,
            "rank_placeholder": self.rank_placeholder,
            "critic": self.critic.to_dict() if self.critic else None,
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class HypothesisGenerationContext:
    analysis_id: str
    organization_id: str
    project_id: str | None = None
    incident_id: str | None = None
    hierarchical_classification: dict[str, Any] = field(default_factory=dict)
    top_classification_candidates: list[dict[str, Any]] = field(default_factory=list)
    open_set_status: str | None = None
    disagreement_result: dict[str, Any] = field(default_factory=dict)
    temporal_primary_failure: dict[str, Any] = field(default_factory=dict)
    downstream_symptom_summary: list[str] = field(default_factory=list)
    graph_consistency_status: str | None = None
    relevant_graph_nodes: list[dict[str, Any]] = field(default_factory=list)
    relevant_graph_edges: list[dict[str, Any]] = field(default_factory=list)
    artifact_availability: list[str] = field(default_factory=list)
    missing_artifacts: list[str] = field(default_factory=list)
    evidence_candidates: list[dict[str, Any]] = field(default_factory=list)
    previous_diagnosis_summary: str | None = None
    combined_text_excerpt: str = ""
    truncation_notes: list[str] = field(default_factory=list)
    parser_novel_signature: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CausalHypothesisRun:
    analysis_id: str
    organization_id: str
    project_id: str | None = None
    incident_id: str | None = None
    status: HypothesisRunStatus = HypothesisRunStatus.DISABLED
    hypotheses: list[CausalHypothesis] = field(default_factory=list)
    deterministic_count: int = 0
    llm_count: int = 0
    invalid_reference_count: int = 0
    duplicate_removed_count: int = 0
    generator_version: str = "hypothesis_pipeline_v1"
    prompt_version: str | None = None
    duration_ms: int | None = None
    warnings: list[str] = field(default_factory=list)
    truncation_notes: list[str] = field(default_factory=list)
    cost_usd: float | None = None
    token_usage: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
    id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "incident_id": self.incident_id,
            "status": self.status.value,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "deterministic_count": self.deterministic_count,
            "llm_count": self.llm_count,
            "invalid_reference_count": self.invalid_reference_count,
            "duplicate_removed_count": self.duplicate_removed_count,
            "generator_version": self.generator_version,
            "prompt_version": self.prompt_version,
            "duration_ms": self.duration_ms,
            "warnings": list(self.warnings),
            "truncation_notes": list(self.truncation_notes),
            "cost_usd": self.cost_usd,
            "token_usage": dict(self.token_usage),
            "created_at": self.created_at.isoformat(),
        }
