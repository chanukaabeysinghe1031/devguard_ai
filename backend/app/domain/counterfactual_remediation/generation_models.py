"""Domain contracts for Phase 6A.6 Part 2 remediation generation (candidates only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.counterfactual_remediation.generation_enums import (
    BlastRadiusLevel,
    CandidatePriorityStatus,
    ConstraintValidationStatus,
    PatchFormat,
    RemediationGenerationStatus,
    RemediationGeneratorType,
    RiskLevel,
)
from app.domain.counterfactual_remediation.generation_versions import (
    REMEDIATION_BLAST_RADIUS_VERSION,
    REMEDIATION_CANDIDATE_PRIORITISER_VERSION,
    REMEDIATION_CONSTRAINT_VALIDATOR_VERSION,
    REMEDIATION_RISK_ANALYSIS_VERSION,
    REMEDIATION_SIDE_EFFECTS_VERSION,
    RULE_REMEDIATION_GENERATOR_VERSION,
)
from app.domain.counterfactual_remediation.models import (
    CounterfactualRemediationCandidate,
    MinimalChangeObjective,
    MinimalChangePlan,
    RemediationConstraint,
    RemediationConstraintSet,
    RemediationCurrentState,
    RemediationRiskSignal,
    RemediationTemplate,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _enum_value(value: Any) -> Any:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else value


def _maybe_to_dict(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    return value


def _list_to_dict(items: list[Any]) -> list[Any]:
    return [_maybe_to_dict(item) for item in items]


@dataclass(slots=True)
class RemediationGenerationContext:
    """Bounded context for Part 2 candidate generation."""

    organization_id: str
    project_id: str
    incident_id: str
    analysis_id: str
    hypothesis_id: str
    remediation_run_id: str
    # Hypothesis
    hypothesis_key: str = ""
    causal_claim: str = ""
    category: str | None = None
    hierarchy: list[str] = field(default_factory=list)
    ranking_score: float | None = None
    support_assessment: dict[str, Any] = field(default_factory=dict)
    contradiction_assessment: dict[str, Any] = field(default_factory=dict)
    evidence_sufficiency: dict[str, Any] | str | None = None
    critic_decision: dict[str, Any] = field(default_factory=dict)
    hypothesis_limitations: list[str] = field(default_factory=list)
    # Current state
    current_state: RemediationCurrentState | dict[str, Any] | None = None
    source_fragment: str | None = None
    content_hash: str | None = None
    failure_condition_summary: str | None = None
    parser_entities: list[dict[str, Any]] = field(default_factory=list)
    graph_node_ids: list[str] = field(default_factory=list)
    graph_edge_ids: list[str] = field(default_factory=list)
    # Constraints / planning
    constraint_set: RemediationConstraintSet | dict[str, Any] | None = None
    blocking_constraints: list[RemediationConstraint] = field(default_factory=list)
    unresolved_conflicts: list[dict[str, Any]] = field(default_factory=list)
    objective: MinimalChangeObjective | dict[str, Any] | None = None
    plan: MinimalChangePlan | dict[str, Any] | None = None
    eligible_templates: list[RemediationTemplate] = field(default_factory=list)
    prohibited_template_ids: list[str] = field(default_factory=list)
    verification_requirements: list[str] = field(default_factory=list)
    rollback_requirements: list[str] = field(default_factory=list)
    # Retrieval
    official_constraints: list[dict[str, Any]] = field(default_factory=list)
    support_candidates: list[dict[str, Any]] = field(default_factory=list)
    contradiction_candidates: list[dict[str, Any]] = field(default_factory=list)
    historical_candidates: list[dict[str, Any]] = field(default_factory=list)
    previous_successful_version: str | None = None
    previous_success_differences: list[dict[str, Any]] = field(default_factory=list)
    # Valid ID allowlists (LLM must not invent outside these)
    valid_artifact_ids: list[str] = field(default_factory=list)
    valid_evidence_ids: list[str] = field(default_factory=list)
    valid_graph_node_ids: list[str] = field(default_factory=list)
    valid_template_ids: list[str] = field(default_factory=list)
    allowed_change_types: list[str] = field(default_factory=list)
    # Security
    redaction_status: str | None = None
    prompt_injection_warnings: list[str] = field(default_factory=list)
    excluded_sensitive_fields: list[str] = field(default_factory=list)
    # Metadata
    missing_information: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "candidates_are_not_verified",
            "generation_does_not_apply_changes",
            "hypothesis_remains_unverified",
        ]
    )
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        sufficiency = self.evidence_sufficiency
        if isinstance(sufficiency, dict):
            sufficiency_out: Any = dict(sufficiency)
        else:
            sufficiency_out = sufficiency
        return {
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "incident_id": self.incident_id,
            "analysis_id": self.analysis_id,
            "hypothesis_id": self.hypothesis_id,
            "remediation_run_id": self.remediation_run_id,
            "hypothesis_key": self.hypothesis_key,
            "causal_claim": self.causal_claim,
            "category": self.category,
            "hierarchy": list(self.hierarchy),
            "ranking_score": self.ranking_score,
            "support_assessment": dict(self.support_assessment),
            "contradiction_assessment": dict(self.contradiction_assessment),
            "evidence_sufficiency": sufficiency_out,
            "critic_decision": dict(self.critic_decision),
            "hypothesis_limitations": list(self.hypothesis_limitations),
            "current_state": (
                dict(self.current_state)
                if isinstance(self.current_state, dict)
                else _maybe_to_dict(self.current_state)
            ),
            "source_fragment": self.source_fragment,
            "content_hash": self.content_hash,
            "failure_condition_summary": self.failure_condition_summary,
            "parser_entities": [dict(e) for e in self.parser_entities],
            "graph_node_ids": list(self.graph_node_ids),
            "graph_edge_ids": list(self.graph_edge_ids),
            "constraint_set": (
                dict(self.constraint_set)
                if isinstance(self.constraint_set, dict)
                else _maybe_to_dict(self.constraint_set)
            ),
            "blocking_constraints": _list_to_dict(self.blocking_constraints),
            "unresolved_conflicts": [dict(c) for c in self.unresolved_conflicts],
            "objective": (
                dict(self.objective)
                if isinstance(self.objective, dict)
                else _maybe_to_dict(self.objective)
            ),
            "plan": (
                dict(self.plan) if isinstance(self.plan, dict) else _maybe_to_dict(self.plan)
            ),
            "eligible_templates": _list_to_dict(self.eligible_templates),
            "prohibited_template_ids": list(self.prohibited_template_ids),
            "verification_requirements": list(self.verification_requirements),
            "rollback_requirements": list(self.rollback_requirements),
            "official_constraints": [dict(c) for c in self.official_constraints],
            "support_candidates": [dict(c) for c in self.support_candidates],
            "contradiction_candidates": [dict(c) for c in self.contradiction_candidates],
            "historical_candidates": [dict(c) for c in self.historical_candidates],
            "previous_successful_version": self.previous_successful_version,
            "previous_success_differences": [
                dict(d) for d in self.previous_success_differences
            ],
            "valid_artifact_ids": list(self.valid_artifact_ids),
            "valid_evidence_ids": list(self.valid_evidence_ids),
            "valid_graph_node_ids": list(self.valid_graph_node_ids),
            "valid_template_ids": list(self.valid_template_ids),
            "allowed_change_types": list(self.allowed_change_types),
            "redaction_status": self.redaction_status,
            "prompt_injection_warnings": list(self.prompt_injection_warnings),
            "excluded_sensitive_fields": list(self.excluded_sensitive_fields),
            "missing_information": list(self.missing_information),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class RemediationGenerationResult:
    """Output of one generator invocation."""

    generator: RemediationGeneratorType | str = RemediationGeneratorType.RULE_TEMPLATE
    status: RemediationGenerationStatus = RemediationGenerationStatus.DISABLED
    candidates: list[CounterfactualRemediationCandidate] = field(default_factory=list)
    rejected_template_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: int | None = None
    generator_version: str = RULE_REMEDIATION_GENERATOR_VERSION
    limitations: list[str] = field(
        default_factory=lambda: [
            "candidates_are_not_verified",
            "generation_does_not_apply_changes",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "generator": _enum_value(self.generator),
            "status": _enum_value(self.status),
            "candidates": _list_to_dict(self.candidates),
            "rejected_template_ids": list(self.rejected_template_ids),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "duration_ms": self.duration_ms,
            "generator_version": self.generator_version,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class CandidateConstraintValidationResult:
    """Structural constraint validation only — not verifier execution."""

    status: ConstraintValidationStatus = ConstraintValidationStatus.INCOMPLETE
    candidate_id: str | None = None
    satisfied_constraints: list[str] = field(default_factory=list)
    unsatisfied_constraints: list[str] = field(default_factory=list)
    unknown_constraints: list[str] = field(default_factory=list)
    blocking_violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    validator_version: str = REMEDIATION_CONSTRAINT_VALIDATOR_VERSION
    limitations: list[str] = field(
        default_factory=lambda: [
            "structural_validation_is_not_independent_verification",
            "candidates_are_not_verified",
        ]
    )
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": _enum_value(self.status),
            "candidate_id": self.candidate_id,
            "satisfied_constraints": list(self.satisfied_constraints),
            "unsatisfied_constraints": list(self.unsatisfied_constraints),
            "unknown_constraints": list(self.unknown_constraints),
            "blocking_violations": list(self.blocking_violations),
            "warnings": list(self.warnings),
            "validator_version": self.validator_version,
            "limitations": list(self.limitations),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class RemediationRiskAssessment:
    """Static risk assessment (not verification confidence)."""

    overall_risk_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    component_scores: dict[str, float] = field(default_factory=dict)
    risk_signals: list[RemediationRiskSignal] | list[dict[str, Any]] = field(
        default_factory=list
    )
    blocking_risks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mitigations: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    version: str = REMEDIATION_RISK_ANALYSIS_VERSION
    limitations: list[str] = field(
        default_factory=lambda: [
            "risk_signals_are_static_heuristics",
            "candidates_are_not_verified",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        signals: list[Any] = []
        for item in self.risk_signals:
            signals.append(_maybe_to_dict(item) if not isinstance(item, dict) else dict(item))
        return {
            "overall_risk_score": self.overall_risk_score,
            "risk_level": _enum_value(self.risk_level),
            "component_scores": dict(self.component_scores),
            "risk_signals": signals,
            "blocking_risks": list(self.blocking_risks),
            "warnings": list(self.warnings),
            "mitigations": list(self.mitigations),
            "unknowns": list(self.unknowns),
            "version": self.version,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class BlastRadiusAssessment:
    """Static blast-radius estimate (not runtime certainty)."""

    level: BlastRadiusLevel = BlastRadiusLevel.UNKNOWN
    artifacts_changed: int = 0
    graph_nodes_potentially_affected: int = 0
    downstream_workflow_jobs: int = 0
    terraform_resources_connected: int = 0
    environments_affected: int = 0
    cross_account_or_region: bool = False
    replacement_or_deletion_potential: bool = False
    affected_entities: list[str] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    version: str = REMEDIATION_BLAST_RADIUS_VERSION
    limitations: list[str] = field(
        default_factory=lambda: [
            "blast_radius_is_static_estimate",
            "no_runtime_certainty",
            "candidates_are_not_verified",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": _enum_value(self.level),
            "artifacts_changed": self.artifacts_changed,
            "graph_nodes_potentially_affected": self.graph_nodes_potentially_affected,
            "downstream_workflow_jobs": self.downstream_workflow_jobs,
            "terraform_resources_connected": self.terraform_resources_connected,
            "environments_affected": self.environments_affected,
            "cross_account_or_region": self.cross_account_or_region,
            "replacement_or_deletion_potential": self.replacement_or_deletion_potential,
            "affected_entities": list(self.affected_entities),
            "reasoning": list(self.reasoning),
            "version": self.version,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class SideEffectAssessment:
    """Possible effects beyond the intended failure-condition change."""

    expected_intended_effects: list[str] = field(default_factory=list)
    potential_side_effects: list[str] = field(default_factory=list)
    unknown_effects: list[str] = field(default_factory=list)
    affected_graph_nodes: list[str] = field(default_factory=list)
    severity: RiskLevel = RiskLevel.UNKNOWN
    evidence_references: list[str] = field(default_factory=list)
    constraint_references: list[str] = field(default_factory=list)
    version: str = REMEDIATION_SIDE_EFFECTS_VERSION
    limitations: list[str] = field(
        default_factory=lambda: [
            "side_effects_are_heuristic",
            "candidates_are_not_verified",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_intended_effects": list(self.expected_intended_effects),
            "potential_side_effects": list(self.potential_side_effects),
            "unknown_effects": list(self.unknown_effects),
            "affected_graph_nodes": list(self.affected_graph_nodes),
            "severity": _enum_value(self.severity),
            "evidence_references": list(self.evidence_references),
            "constraint_references": list(self.constraint_references),
            "version": self.version,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class RemediationCandidateQualityAssessment:
    """Priority scoring components — NEVER verification/causal confidence."""

    candidate_id: str | None = None
    candidate_priority_score: float = 0.0
    components: dict[str, float] = field(default_factory=dict)
    penalties: dict[str, float] = field(default_factory=dict)
    version: str = REMEDIATION_CANDIDATE_PRIORITISER_VERSION
    limitations: list[str] = field(
        default_factory=lambda: [
            "candidate_priority_score_is_not_verification_confidence",
            "candidate_priority_score_is_not_causal_confidence",
            "candidate_priority_score_is_not_success_probability",
            "candidates_are_not_verified",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_priority_score": self.candidate_priority_score,
            "components": dict(self.components),
            "penalties": dict(self.penalties),
            "version": self.version,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class PrioritisationResult:
    """Ordered unverified candidates for later verification."""

    ordered_candidate_ids: list[str] = field(default_factory=list)
    priority_statuses: dict[str, CandidatePriorityStatus | str] = field(default_factory=dict)
    quality_assessments: list[RemediationCandidateQualityAssessment] = field(
        default_factory=list
    )
    selected_for_verification: list[str] = field(default_factory=list)
    no_safe_candidate: bool = False
    warnings: list[str] = field(default_factory=list)
    version: str = REMEDIATION_CANDIDATE_PRIORITISER_VERSION
    limitations: list[str] = field(
        default_factory=lambda: [
            "prioritisation_is_not_selection_of_the_fix",
            "candidates_are_not_verified",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordered_candidate_ids": list(self.ordered_candidate_ids),
            "priority_statuses": {
                k: _enum_value(v) for k, v in self.priority_statuses.items()
            },
            "quality_assessments": _list_to_dict(self.quality_assessments),
            "selected_for_verification": list(self.selected_for_verification),
            "no_safe_candidate": self.no_safe_candidate,
            "warnings": list(self.warnings),
            "version": self.version,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class RenderedPatch:
    """In-memory rendered patch — never mutates disk."""

    patch_format: PatchFormat = PatchFormat.UNSUPPORTED
    normalized_diff: str | None = None
    original_fragment: str | None = None
    proposed_fragment: str | None = None
    content_hash_before: str | None = None
    content_hash_after: str | None = None
    changed_line_count: int = 0
    incomplete: bool = False
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "patch_rendering_is_not_semantic_verification",
            "candidates_are_not_verified",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "patch_format": _enum_value(self.patch_format),
            "normalized_diff": self.normalized_diff,
            "original_fragment": self.original_fragment,
            "proposed_fragment": self.proposed_fragment,
            "content_hash_before": self.content_hash_before,
            "content_hash_after": self.content_hash_after,
            "changed_line_count": self.changed_line_count,
            "incomplete": self.incomplete,
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
        }
