"""Domain contracts for Phase 6A.6 Part 1 counterfactual remediation (candidates only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.counterfactual_remediation.enums import (
    CandidateStructuralValidationStatus,
    ConstraintExtractionStatus,
    ConstraintSatisfactionStatus,
    ConstraintSetCompleteness,
    ConstraintSeverity,
    ConstraintSourceType,
    ConstraintType,
    CounterfactualCandidateStatus,
    CounterfactualChangeType,
    CounterfactualRemediationRunStatus,
    ExpectedFailureConditionStatus,
    HypothesisEligibilityStatus,
    MinimalChangePlanStatus,
    PreconditionStatus,
    RemediationArtifactType,
    RemediationRiskType,
    RollbackType,
    VerifierType,
)
from app.domain.counterfactual_remediation.versions import (
    CONSTRAINT_EXTRACTOR_VERSION,
    COUNTERFACTUAL_CONTEXT_VERSION,
    COUNTERFACTUAL_REMEDIATION_SNAPSHOT_VERSION,
    COUNTERFACTUAL_STATE_VERSION,
    MINIMAL_CHANGE_PLANNER_VERSION,
    REMEDIATION_CANDIDATE_VALIDATOR_VERSION,
    REMEDIATION_CONSTRAINTS_VERSION,
    REMEDIATION_CURRENT_STATE_VERSION,
    REMEDIATION_TEMPLATES_VERSION,
)

# Ordered heuristic priorities for minimal-change planning (Section 26).
OPTIMIZATION_PRIORITIES: tuple[str, ...] = (
    "remove_predicted_failure_condition",
    "satisfy_blocking_constraints",
    "minimize_changed_files",
    "minimize_changed_lines",
    "minimize_permission_expansion",
    "minimize_resource_replacement",
    "preserve_existing_behavior",
    "preserve_security_controls",
    "preserve_rollback",
    "avoid_unrelated_modifications",
)

_DEFAULT_CANDIDATE_LIMITATIONS: tuple[str, ...] = (
    "candidates_are_not_verified",
    "candidates_are_not_applied",
    "no_runtime_verification_in_part1",
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
class CounterfactualRemediationRun:
    """Groups remediation foundation work for one analysis (candidates only)."""

    id: str
    organization_id: str
    project_id: str
    incident_id: str
    analysis_id: str
    status: CounterfactualRemediationRunStatus = CounterfactualRemediationRunStatus.PENDING
    hypothesis_ranking_run_id: str | None = None
    selected_hypothesis_ids: list[str] = field(default_factory=list)
    selected_hypothesis_count: int = 0
    candidate_count: int = 0
    safe_candidate_count: int = 0
    incomplete_candidate_count: int = 0
    rejected_candidate_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    context_version: str = COUNTERFACTUAL_CONTEXT_VERSION
    constraint_version: str = REMEDIATION_CONSTRAINTS_VERSION
    planner_version: str = MINIMAL_CHANGE_PLANNER_VERSION
    template_registry_version: str = REMEDIATION_TEMPLATES_VERSION
    configuration_snapshot: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "candidates_are_not_verified",
            "run_does_not_imply_application_or_verification",
            *_DEFAULT_CANDIDATE_LIMITATIONS[2:],
        ]
    )
    snapshot_version: str = COUNTERFACTUAL_REMEDIATION_SNAPSHOT_VERSION
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "incident_id": self.incident_id,
            "analysis_id": self.analysis_id,
            "hypothesis_ranking_run_id": self.hypothesis_ranking_run_id,
            "status": _enum_value(self.status),
            "selected_hypothesis_ids": list(self.selected_hypothesis_ids),
            "selected_hypothesis_count": self.selected_hypothesis_count,
            "candidate_count": self.candidate_count,
            "safe_candidate_count": self.safe_candidate_count,
            "incomplete_candidate_count": self.incomplete_candidate_count,
            "rejected_candidate_count": self.rejected_candidate_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "context_version": self.context_version,
            "constraint_version": self.constraint_version,
            "planner_version": self.planner_version,
            "template_registry_version": self.template_registry_version,
            "configuration_snapshot": dict(self.configuration_snapshot),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "limitations": list(self.limitations),
            "snapshot_version": self.snapshot_version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(slots=True)
class CounterfactualRemediationContext:
    """Bounded, masked context for hypothesis-conditional remediation planning."""

    organization_id: str
    project_id: str
    incident_id: str
    analysis_id: str
    hypothesis_id: str
    # Hypothesis
    hypothesis_key: str = ""
    category: str | None = None
    hierarchy: list[str] = field(default_factory=list)
    title: str = ""
    causal_claim: str = ""
    generation_prior: float | None = None
    ranking_score: float | None = None
    candidate_selection_status: str | None = None
    support_assessment: dict[str, Any] = field(default_factory=dict)
    contradiction_assessment: dict[str, Any] = field(default_factory=dict)
    evidence_sufficiency: dict[str, Any] | str | None = None
    critic_result: dict[str, Any] = field(default_factory=dict)
    hypothesis_limitations: list[str] = field(default_factory=list)
    # Failure state
    observed_failure_node: str | None = None
    primary_temporal_event: str | None = None
    failure_signature: str | None = None
    error_code: str | None = None
    failed_workflow_job_step: str | None = None
    affected_command: str | None = None
    affected_resource: str | None = None
    failure_condition_summary: str | None = None
    downstream_symptoms: list[str] = field(default_factory=list)
    # Graph
    root_cause_node: str | None = None
    causal_path_nodes: list[str] = field(default_factory=list)
    causal_path_edges: list[str] = field(default_factory=list)
    related_artifact_nodes: list[str] = field(default_factory=list)
    related_policy_nodes: list[str] = field(default_factory=list)
    related_resource_nodes: list[str] = field(default_factory=list)
    graph_consistency_status: str | None = None
    graph_warnings: list[str] = field(default_factory=list)
    missing_graph_links: list[str] = field(default_factory=list)
    # Artifacts
    affected_artifact: str | None = None
    source_path: str | None = None
    line_range: tuple[int, int] | list[int] | None = None
    parser_entities: list[dict[str, Any]] = field(default_factory=list)
    current_configuration_fragment: str | None = None
    related_changed_files: list[str] = field(default_factory=list)
    previous_successful_version: str | None = None
    artifact_quality: str | None = None
    missing_artifacts: list[str] = field(default_factory=list)
    # Retrieval
    top_validated_evidence_candidates: list[dict[str, Any]] = field(default_factory=list)
    official_constraints: list[dict[str, Any]] = field(default_factory=list)
    historical_candidates: list[dict[str, Any]] = field(default_factory=list)
    support_candidates: list[dict[str, Any]] = field(default_factory=list)
    contradiction_candidates: list[dict[str, Any]] = field(default_factory=list)
    source_provenance: list[dict[str, Any]] = field(default_factory=list)
    # Open-set and disagreement
    open_set_status: str | None = None
    classifier_disagreement: dict[str, Any] = field(default_factory=dict)
    hypothesis_tie_or_weak_evidence_status: str | None = None
    # Security
    redaction_status: str | None = None
    excluded_sensitive_fields: list[str] = field(default_factory=list)
    prompt_injection_warnings: list[str] = field(default_factory=list)
    # Metadata
    context_version: str = COUNTERFACTUAL_CONTEXT_VERSION
    size: int | None = None
    truncation_details: dict[str, Any] = field(default_factory=dict)
    missing_information: list[str] = field(default_factory=list)
    assumptions_allowed: list[str] = field(default_factory=list)
    assumptions_prohibited: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "candidates_are_not_verified",
            "context_excludes_unrestricted_logs_and_credentials",
            "no_fabricated_configuration_fragments",
        ]
    )
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        line_range: list[int] | None
        if self.line_range is None:
            line_range = None
        elif isinstance(self.line_range, tuple):
            line_range = list(self.line_range)
        else:
            line_range = list(self.line_range)
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
            "hypothesis_key": self.hypothesis_key,
            "category": self.category,
            "hierarchy": list(self.hierarchy),
            "title": self.title,
            "causal_claim": self.causal_claim,
            "generation_prior": self.generation_prior,
            "ranking_score": self.ranking_score,
            "candidate_selection_status": self.candidate_selection_status,
            "support_assessment": dict(self.support_assessment),
            "contradiction_assessment": dict(self.contradiction_assessment),
            "evidence_sufficiency": sufficiency_out,
            "critic_result": dict(self.critic_result),
            "hypothesis_limitations": list(self.hypothesis_limitations),
            "observed_failure_node": self.observed_failure_node,
            "primary_temporal_event": self.primary_temporal_event,
            "failure_signature": self.failure_signature,
            "error_code": self.error_code,
            "failed_workflow_job_step": self.failed_workflow_job_step,
            "affected_command": self.affected_command,
            "affected_resource": self.affected_resource,
            "failure_condition_summary": self.failure_condition_summary,
            "downstream_symptoms": list(self.downstream_symptoms),
            "root_cause_node": self.root_cause_node,
            "causal_path_nodes": list(self.causal_path_nodes),
            "causal_path_edges": list(self.causal_path_edges),
            "related_artifact_nodes": list(self.related_artifact_nodes),
            "related_policy_nodes": list(self.related_policy_nodes),
            "related_resource_nodes": list(self.related_resource_nodes),
            "graph_consistency_status": self.graph_consistency_status,
            "graph_warnings": list(self.graph_warnings),
            "missing_graph_links": list(self.missing_graph_links),
            "affected_artifact": self.affected_artifact,
            "source_path": self.source_path,
            "line_range": line_range,
            "parser_entities": [dict(e) for e in self.parser_entities],
            "current_configuration_fragment": self.current_configuration_fragment,
            "related_changed_files": list(self.related_changed_files),
            "previous_successful_version": self.previous_successful_version,
            "artifact_quality": self.artifact_quality,
            "missing_artifacts": list(self.missing_artifacts),
            "top_validated_evidence_candidates": [
                dict(c) for c in self.top_validated_evidence_candidates
            ],
            "official_constraints": [dict(c) for c in self.official_constraints],
            "historical_candidates": [dict(c) for c in self.historical_candidates],
            "support_candidates": [dict(c) for c in self.support_candidates],
            "contradiction_candidates": [dict(c) for c in self.contradiction_candidates],
            "source_provenance": [dict(p) for p in self.source_provenance],
            "open_set_status": self.open_set_status,
            "classifier_disagreement": dict(self.classifier_disagreement),
            "hypothesis_tie_or_weak_evidence_status": self.hypothesis_tie_or_weak_evidence_status,
            "redaction_status": self.redaction_status,
            "excluded_sensitive_fields": list(self.excluded_sensitive_fields),
            "prompt_injection_warnings": list(self.prompt_injection_warnings),
            "context_version": self.context_version,
            "size": self.size,
            "truncation_details": dict(self.truncation_details),
            "missing_information": list(self.missing_information),
            "assumptions_allowed": list(self.assumptions_allowed),
            "assumptions_prohibited": list(self.assumptions_prohibited),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class RemediationCurrentState:
    """Relevant pre-change system state (bounded fragments + hashes)."""

    artifact_id: str | None = None
    artifact_type: RemediationArtifactType | str | None = None
    source_path: str | None = None
    commit_sha: str | None = None
    content_hash: str | None = None
    source_fragment: str | None = None
    structured_entities: list[dict[str, Any]] = field(default_factory=list)
    structured_relationships: list[dict[str, Any]] = field(default_factory=list)
    current_values: dict[str, Any] = field(default_factory=dict)
    current_references: dict[str, Any] = field(default_factory=dict)
    current_dependencies: list[dict[str, Any]] = field(default_factory=list)
    current_permissions: list[dict[str, Any]] = field(default_factory=list)
    current_conditions: list[dict[str, Any]] = field(default_factory=list)
    current_region: str | None = None
    current_account_context: str | None = None
    current_environment: str | None = None
    current_versions: dict[str, Any] = field(default_factory=dict)
    current_security_findings: list[dict[str, Any]] = field(default_factory=list)
    current_plan_changes: list[dict[str, Any]] = field(default_factory=list)
    current_failure_condition: str | None = None
    parser_version: str | None = None
    extraction_quality: str | None = None
    missing_fields: list[str] = field(default_factory=list)
    redaction_status: str | None = None
    state_version: str = REMEDIATION_CURRENT_STATE_VERSION
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "current_state_is_not_verified_runtime_state",
            "fragments_only_full_files_not_persisted_by_default",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": _enum_value(self.artifact_type),
            "source_path": self.source_path,
            "commit_sha": self.commit_sha,
            "content_hash": self.content_hash,
            "source_fragment": self.source_fragment,
            "structured_entities": [dict(e) for e in self.structured_entities],
            "structured_relationships": [dict(r) for r in self.structured_relationships],
            "current_values": dict(self.current_values),
            "current_references": dict(self.current_references),
            "current_dependencies": [dict(d) for d in self.current_dependencies],
            "current_permissions": [dict(p) for p in self.current_permissions],
            "current_conditions": [dict(c) for c in self.current_conditions],
            "current_region": self.current_region,
            "current_account_context": self.current_account_context,
            "current_environment": self.current_environment,
            "current_versions": dict(self.current_versions),
            "current_security_findings": [dict(f) for f in self.current_security_findings],
            "current_plan_changes": [dict(c) for c in self.current_plan_changes],
            "current_failure_condition": self.current_failure_condition,
            "parser_version": self.parser_version,
            "extraction_quality": self.extraction_quality,
            "missing_fields": list(self.missing_fields),
            "redaction_status": self.redaction_status,
            "state_version": self.state_version,
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class RemediationCounterfactualState:
    """Hypothetical post-change state expected if a candidate were applied."""

    candidate_id: str | None = None
    artifact_id: str | None = None
    artifact_type: RemediationArtifactType | str | None = None
    proposed_values: dict[str, Any] = field(default_factory=dict)
    proposed_references: dict[str, Any] = field(default_factory=dict)
    proposed_dependencies: list[dict[str, Any]] = field(default_factory=list)
    proposed_permissions: list[dict[str, Any]] = field(default_factory=list)
    proposed_conditions: list[dict[str, Any]] = field(default_factory=list)
    proposed_region: str | None = None
    proposed_environment: str | None = None
    proposed_versions: dict[str, Any] = field(default_factory=dict)
    proposed_security_properties: dict[str, Any] = field(default_factory=dict)
    expected_failure_condition_status: ExpectedFailureConditionStatus = (
        ExpectedFailureConditionStatus.UNKNOWN
    )
    expected_preserved_behaviors: list[str] = field(default_factory=list)
    expected_changed_behaviors: list[str] = field(default_factory=list)
    expected_unaffected_artifacts: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    unknown_effects: list[str] = field(default_factory=list)
    state_version: str = COUNTERFACTUAL_STATE_VERSION
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "expected_effects_are_not_verified",
            "candidates_are_not_verified",
            "status_is_not_fixed_or_resolved",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "artifact_id": self.artifact_id,
            "artifact_type": _enum_value(self.artifact_type),
            "proposed_values": dict(self.proposed_values),
            "proposed_references": dict(self.proposed_references),
            "proposed_dependencies": [dict(d) for d in self.proposed_dependencies],
            "proposed_permissions": [dict(p) for p in self.proposed_permissions],
            "proposed_conditions": [dict(c) for c in self.proposed_conditions],
            "proposed_region": self.proposed_region,
            "proposed_environment": self.proposed_environment,
            "proposed_versions": dict(self.proposed_versions),
            "proposed_security_properties": dict(self.proposed_security_properties),
            "expected_failure_condition_status": _enum_value(
                self.expected_failure_condition_status
            ),
            "expected_preserved_behaviors": list(self.expected_preserved_behaviors),
            "expected_changed_behaviors": list(self.expected_changed_behaviors),
            "expected_unaffected_artifacts": list(self.expected_unaffected_artifacts),
            "assumptions": list(self.assumptions),
            "unknown_effects": list(self.unknown_effects),
            "state_version": self.state_version,
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class CounterfactualChange:
    """Single bounded structured or textual change under a candidate."""

    id: str
    candidate_id: str | None = None
    artifact_id: str | None = None
    artifact_type: RemediationArtifactType | str | None = None
    source_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    change_type: CounterfactualChangeType | str = CounterfactualChangeType.UNKNOWN
    target_entity_id: str | None = None
    target_property: str | None = None
    original_fragment: str | None = None
    proposed_fragment: str | None = None
    normalized_diff: str | None = None
    expected_effect: str | None = None
    expected_failure_condition_removed: bool | None = None
    rationale: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    graph_node_ids: list[str] = field(default_factory=list)
    graph_edge_ids: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "change_is_not_verified",
            "candidates_are_not_verified",
        ]
    )
    change_order: int = 0
    content_hash_before: str | None = None
    content_hash_after_candidate: str | None = None
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "artifact_id": self.artifact_id,
            "artifact_type": _enum_value(self.artifact_type),
            "source_path": self.source_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "change_type": _enum_value(self.change_type),
            "target_entity_id": self.target_entity_id,
            "target_property": self.target_property,
            "original_fragment": self.original_fragment,
            "proposed_fragment": self.proposed_fragment,
            "normalized_diff": self.normalized_diff,
            "expected_effect": self.expected_effect,
            "expected_failure_condition_removed": self.expected_failure_condition_removed,
            "rationale": self.rationale,
            "evidence_ids": list(self.evidence_ids),
            "graph_node_ids": list(self.graph_node_ids),
            "graph_edge_ids": list(self.graph_edge_ids),
            "assumptions": list(self.assumptions),
            "limitations": list(self.limitations),
            "change_order": self.change_order,
            "content_hash_before": self.content_hash_before,
            "content_hash_after_candidate": self.content_hash_after_candidate,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class RemediationConstraint:
    """Single deterministic constraint extracted for remediation planning."""

    id: str
    organization_id: str
    project_id: str
    incident_id: str
    analysis_id: str
    hypothesis_id: str
    constraint_key: str
    constraint_type: ConstraintType | str
    severity: ConstraintSeverity | str = ConstraintSeverity.INFORMATIONAL
    source_type: ConstraintSourceType | str = ConstraintSourceType.UNKNOWN
    candidate_id: str | None = None
    source_artifact_id: str | None = None
    source_graph_node_id: str | None = None
    source_graph_edge_id: str | None = None
    source_evidence_id: str | None = None
    source_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    description: str = ""
    machine_readable_rule: dict[str, Any] = field(default_factory=dict)
    expected_value: Any = None
    prohibited_value: Any = None
    scope: str | None = None
    confidence: float = 0.0
    extraction_method: str = "deterministic"
    extractor_version: str = CONSTRAINT_EXTRACTOR_VERSION
    is_blocking: bool = False
    is_satisfied: bool | None = None
    satisfaction_status: ConstraintSatisfactionStatus = ConstraintSatisfactionStatus.NOT_EVALUATED
    limitations: list[str] = field(
        default_factory=lambda: [
            "satisfaction_is_structural_only",
            "no_verifier_based_satisfaction_in_part1",
        ]
    )
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "incident_id": self.incident_id,
            "analysis_id": self.analysis_id,
            "hypothesis_id": self.hypothesis_id,
            "candidate_id": self.candidate_id,
            "constraint_key": self.constraint_key,
            "constraint_type": _enum_value(self.constraint_type),
            "severity": _enum_value(self.severity),
            "source_type": _enum_value(self.source_type),
            "source_artifact_id": self.source_artifact_id,
            "source_graph_node_id": self.source_graph_node_id,
            "source_graph_edge_id": self.source_graph_edge_id,
            "source_evidence_id": self.source_evidence_id,
            "source_path": self.source_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "description": self.description,
            "machine_readable_rule": dict(self.machine_readable_rule),
            "expected_value": self.expected_value,
            "prohibited_value": self.prohibited_value,
            "scope": self.scope,
            "confidence": self.confidence,
            "extraction_method": self.extraction_method,
            "extractor_version": self.extractor_version,
            "is_blocking": self.is_blocking,
            "is_satisfied": self.is_satisfied,
            "satisfaction_status": _enum_value(self.satisfaction_status),
            "limitations": list(self.limitations),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class ConstraintConflict:
    """Detected conflict between constraints (no automatic LLM resolution)."""

    id: str
    involved_constraint_ids: list[str] = field(default_factory=list)
    severity: ConstraintSeverity | str = ConstraintSeverity.BLOCKING
    explanation: str = ""
    must_stop_generation: bool = True
    missing_evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "conflicts_are_not_auto_resolved",
            "candidates_are_not_verified",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "involved_constraint_ids": list(self.involved_constraint_ids),
            "severity": _enum_value(self.severity),
            "explanation": self.explanation,
            "must_stop_generation": self.must_stop_generation,
            "missing_evidence": list(self.missing_evidence),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class RemediationConstraintSet:
    """Grouped constraints for one hypothesis (optionally one candidate)."""

    hypothesis_id: str
    candidate_id: str | None = None
    constraints: list[RemediationConstraint] = field(default_factory=list)
    blocking_constraints: list[RemediationConstraint] = field(default_factory=list)
    security_constraints: list[RemediationConstraint] = field(default_factory=list)
    workflow_constraints: list[RemediationConstraint] = field(default_factory=list)
    terraform_constraints: list[RemediationConstraint] = field(default_factory=list)
    cloud_constraints: list[RemediationConstraint] = field(default_factory=list)
    repository_constraints: list[RemediationConstraint] = field(default_factory=list)
    operational_constraints: list[RemediationConstraint] = field(default_factory=list)
    conflicts: list[ConstraintConflict] = field(default_factory=list)
    missing_constraint_sources: list[str] = field(default_factory=list)
    extraction_warnings: list[str] = field(default_factory=list)
    extraction_errors: list[str] = field(default_factory=list)
    extraction_version: str = REMEDIATION_CONSTRAINTS_VERSION
    completeness: ConstraintSetCompleteness = ConstraintSetCompleteness.INSUFFICIENT
    limitations: list[str] = field(
        default_factory=lambda: [
            "constraint_completeness_is_not_evidence_sufficiency",
            "candidates_are_not_verified",
        ]
    )
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "candidate_id": self.candidate_id,
            "constraints": _list_to_dict(self.constraints),
            "blocking_constraints": _list_to_dict(self.blocking_constraints),
            "security_constraints": _list_to_dict(self.security_constraints),
            "workflow_constraints": _list_to_dict(self.workflow_constraints),
            "terraform_constraints": _list_to_dict(self.terraform_constraints),
            "cloud_constraints": _list_to_dict(self.cloud_constraints),
            "repository_constraints": _list_to_dict(self.repository_constraints),
            "operational_constraints": _list_to_dict(self.operational_constraints),
            "conflicts": _list_to_dict(self.conflicts),
            "missing_constraint_sources": list(self.missing_constraint_sources),
            "extraction_warnings": list(self.extraction_warnings),
            "extraction_errors": list(self.extraction_errors),
            "extraction_version": self.extraction_version,
            "completeness": _enum_value(self.completeness),
            "limitations": list(self.limitations),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class ConstraintExtractionResult:
    """Result of one constraint extractor invocation."""

    extractor_name: str
    status: ConstraintExtractionStatus = ConstraintExtractionStatus.NO_CONSTRAINTS
    constraints: list[RemediationConstraint] = field(default_factory=list)
    artifact_ids_processed: list[str] = field(default_factory=list)
    extracted_count: int = 0
    blocking_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: int | None = None
    extractor_version: str = CONSTRAINT_EXTRACTOR_VERSION
    limitations: list[str] = field(
        default_factory=lambda: [
            "no_fake_constraints",
            "candidates_are_not_verified",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "extractor_name": self.extractor_name,
            "status": _enum_value(self.status),
            "constraints": _list_to_dict(self.constraints),
            "artifact_ids_processed": list(self.artifact_ids_processed),
            "extracted_count": self.extracted_count,
            "blocking_count": self.blocking_count,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "duration_ms": self.duration_ms,
            "extractor_version": self.extractor_version,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class CounterfactualPrecondition:
    """Required/optional precondition for generating a hypothesis-linked candidate."""

    id: str
    hypothesis_id: str
    condition_type: str
    description: str = ""
    expected_current_state: str | dict[str, Any] | None = None
    actual_current_state: str | dict[str, Any] | None = None
    status: PreconditionStatus = PreconditionStatus.UNKNOWN
    evidence_ids: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    graph_node_ids: list[str] = field(default_factory=list)
    is_required: bool = True
    limitations: list[str] = field(
        default_factory=lambda: [
            "unsatisfied_required_preconditions_block_specific_patches",
            "candidates_are_not_verified",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        expected = self.expected_current_state
        actual = self.actual_current_state
        return {
            "id": self.id,
            "hypothesis_id": self.hypothesis_id,
            "condition_type": self.condition_type,
            "description": self.description,
            "expected_current_state": dict(expected) if isinstance(expected, dict) else expected,
            "actual_current_state": dict(actual) if isinstance(actual, dict) else actual,
            "status": _enum_value(self.status),
            "evidence_ids": list(self.evidence_ids),
            "artifact_ids": list(self.artifact_ids),
            "graph_node_ids": list(self.graph_node_ids),
            "is_required": self.is_required,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class CounterfactualFailureCondition:
    """Observed failure condition and expected post-change condition (expected language)."""

    condition_id: str
    hypothesis_id: str
    observed_condition: str = ""
    condition_type: str = ""
    triggering_action: str | None = None
    affected_resource: str | None = None
    active_principal: str | None = None
    affected_artifact: str | None = None
    expected_condition_after_change: str | None = None
    measurable_static_indicator: str | None = None
    required_verifier_types: list[VerifierType | str] = field(default_factory=list)
    confidence: float = 0.0
    limitations: list[str] = field(
        default_factory=lambda: [
            "expected_condition_is_not_runtime_guarantee",
            "candidates_are_not_verified",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition_id": self.condition_id,
            "hypothesis_id": self.hypothesis_id,
            "observed_condition": self.observed_condition,
            "condition_type": self.condition_type,
            "triggering_action": self.triggering_action,
            "affected_resource": self.affected_resource,
            "active_principal": self.active_principal,
            "affected_artifact": self.affected_artifact,
            "expected_condition_after_change": self.expected_condition_after_change,
            "measurable_static_indicator": self.measurable_static_indicator,
            "required_verifier_types": [_enum_value(v) for v in self.required_verifier_types],
            "confidence": self.confidence,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class MinimalChangeObjective:
    """Heuristic objective for minimal-change planning under constraints."""

    hypothesis_id: str
    primary_target: str | None = None
    primary_property: str | None = None
    desired_state: str | dict[str, Any] | None = None
    maximum_files: int = 1
    maximum_changed_lines: int = 50
    allowed_artifact_types: list[RemediationArtifactType | str] = field(default_factory=list)
    prohibited_artifact_types: list[RemediationArtifactType | str] = field(default_factory=list)
    preserve_behaviors: list[str] = field(default_factory=list)
    avoid_side_effects: list[str] = field(default_factory=list)
    required_constraints: list[str] = field(default_factory=list)
    optimization_priorities: list[str] = field(
        default_factory=lambda: list(OPTIMIZATION_PRIORITIES)
    )
    objective_version: str = MINIMAL_CHANGE_PLANNER_VERSION
    limitations: list[str] = field(
        default_factory=lambda: [
            "priorities_are_heuristic_not_mathematical_optima",
            "candidates_are_not_verified",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        desired = self.desired_state
        return {
            "hypothesis_id": self.hypothesis_id,
            "primary_target": self.primary_target,
            "primary_property": self.primary_property,
            "desired_state": dict(desired) if isinstance(desired, dict) else desired,
            "maximum_files": self.maximum_files,
            "maximum_changed_lines": self.maximum_changed_lines,
            "allowed_artifact_types": [_enum_value(t) for t in self.allowed_artifact_types],
            "prohibited_artifact_types": [_enum_value(t) for t in self.prohibited_artifact_types],
            "preserve_behaviors": list(self.preserve_behaviors),
            "avoid_side_effects": list(self.avoid_side_effects),
            "required_constraints": list(self.required_constraints),
            "optimization_priorities": list(self.optimization_priorities),
            "objective_version": self.objective_version,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class MinimalChangePlan:
    """Deterministic planning skeleton output (full generation is Part 2)."""

    hypothesis_id: str
    candidate_plan_key: str = ""
    target_artifacts: list[str] = field(default_factory=list)
    proposed_change_types: list[CounterfactualChangeType | str] = field(default_factory=list)
    proposed_properties: list[str] = field(default_factory=list)
    change_sequence: list[dict[str, Any]] = field(default_factory=list)
    constraints_considered: list[str] = field(default_factory=list)
    blocking_constraints: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    expected_effects: list[str] = field(default_factory=list)
    expected_preserved_behaviors: list[str] = field(default_factory=list)
    rollback_requirements: list[str] = field(default_factory=list)
    incomplete_information: list[str] = field(default_factory=list)
    planner_version: str = MINIMAL_CHANGE_PLANNER_VERSION
    status: MinimalChangePlanStatus = MinimalChangePlanStatus.INCOMPLETE
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "plan_is_not_an_applied_patch",
            "candidates_are_not_verified",
            "full_generation_deferred_to_part2",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "candidate_plan_key": self.candidate_plan_key,
            "target_artifacts": list(self.target_artifacts),
            "proposed_change_types": [_enum_value(t) for t in self.proposed_change_types],
            "proposed_properties": list(self.proposed_properties),
            "change_sequence": [dict(s) for s in self.change_sequence],
            "constraints_considered": list(self.constraints_considered),
            "blocking_constraints": list(self.blocking_constraints),
            "assumptions": list(self.assumptions),
            "expected_effects": list(self.expected_effects),
            "expected_preserved_behaviors": list(self.expected_preserved_behaviors),
            "rollback_requirements": list(self.rollback_requirements),
            "incomplete_information": list(self.incomplete_information),
            "planner_version": self.planner_version,
            "status": _enum_value(self.status),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class RemediationTemplate:
    """Versioned remediation template contract (registry builders may be stubs)."""

    template_id: str
    template_version: str = REMEDIATION_TEMPLATES_VERSION
    category_codes: list[str] = field(default_factory=list)
    hierarchy_paths: list[str] = field(default_factory=list)
    supported_hypothesis_patterns: list[str] = field(default_factory=list)
    supported_artifact_types: list[RemediationArtifactType | str] = field(default_factory=list)
    required_preconditions: list[str] = field(default_factory=list)
    optional_preconditions: list[str] = field(default_factory=list)
    prohibited_conditions: list[str] = field(default_factory=list)
    required_constraints: list[str] = field(default_factory=list)
    change_type: CounterfactualChangeType | str = CounterfactualChangeType.UNKNOWN
    target_selector_rules: list[dict[str, Any]] = field(default_factory=list)
    current_state_requirements: list[str] = field(default_factory=list)
    counterfactual_state_builder: str | None = None
    expected_effects: list[str] = field(default_factory=list)
    expected_preserved_behaviors: list[str] = field(default_factory=list)
    default_verification_requirements: list[str] = field(default_factory=list)
    default_rollback_strategy: RollbackType | str = RollbackType.NOT_AVAILABLE
    risk_notes: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "template_does_not_verify_remediation",
            "candidates_are_not_verified",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_version": self.template_version,
            "category_codes": list(self.category_codes),
            "hierarchy_paths": list(self.hierarchy_paths),
            "supported_hypothesis_patterns": list(self.supported_hypothesis_patterns),
            "supported_artifact_types": [_enum_value(t) for t in self.supported_artifact_types],
            "required_preconditions": list(self.required_preconditions),
            "optional_preconditions": list(self.optional_preconditions),
            "prohibited_conditions": list(self.prohibited_conditions),
            "required_constraints": list(self.required_constraints),
            "change_type": _enum_value(self.change_type),
            "target_selector_rules": [dict(r) for r in self.target_selector_rules],
            "current_state_requirements": list(self.current_state_requirements),
            "counterfactual_state_builder": self.counterfactual_state_builder,
            "expected_effects": list(self.expected_effects),
            "expected_preserved_behaviors": list(self.expected_preserved_behaviors),
            "default_verification_requirements": list(self.default_verification_requirements),
            "default_rollback_strategy": _enum_value(self.default_rollback_strategy),
            "risk_notes": list(self.risk_notes),
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class RemediationVerificationRequirement:
    """Reserved verification requirement — not executed in Part 1."""

    requirement_id: str
    candidate_id: str | None = None
    verifier_type: VerifierType | str = VerifierType.COUNTERFACTUAL_FAILURE_CONDITION
    required: bool = True
    reason: str = ""
    expected_check: str | None = None
    expected_success_condition: str | None = None
    blocking_on_failure: bool = True
    input_artifacts: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "verifiers_are_not_executed_in_part1",
            "candidates_are_not_verified",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "candidate_id": self.candidate_id,
            "verifier_type": _enum_value(self.verifier_type),
            "required": self.required,
            "reason": self.reason,
            "expected_check": self.expected_check,
            "expected_success_condition": self.expected_success_condition,
            "blocking_on_failure": self.blocking_on_failure,
            "input_artifacts": list(self.input_artifacts),
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class RemediationRollbackPlan:
    """Structured rollback plan (no shell commands)."""

    candidate_id: str | None = None
    rollback_type: RollbackType | str = RollbackType.NOT_AVAILABLE
    original_content_hashes: list[str] = field(default_factory=list)
    affected_artifacts: list[str] = field(default_factory=list)
    rollback_steps: list[dict[str, Any]] = field(default_factory=list)
    rollback_preconditions: list[str] = field(default_factory=list)
    rollback_limitations: list[str] = field(default_factory=list)
    rollback_risk: str | None = None
    can_restore_exactly: bool = False
    limitations: list[str] = field(
        default_factory=lambda: [
            "rollback_plan_is_not_executed",
            "candidates_are_not_verified",
        ]
    )
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "rollback_type": _enum_value(self.rollback_type),
            "original_content_hashes": list(self.original_content_hashes),
            "affected_artifacts": list(self.affected_artifacts),
            "rollback_steps": [dict(s) for s in self.rollback_steps],
            "rollback_preconditions": list(self.rollback_preconditions),
            "rollback_limitations": list(self.rollback_limitations),
            "rollback_risk": self.rollback_risk,
            "can_restore_exactly": self.can_restore_exactly,
            "limitations": list(self.limitations),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class RemediationRiskSignal:
    """Static risk signal contract (full risk engine is Part 2)."""

    risk_type: RemediationRiskType | str
    severity: ConstraintSeverity | str = ConstraintSeverity.MEDIUM
    description: str = ""
    source: str | None = None
    affected_artifact: str | None = None
    affected_resource: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    constraint_ids: list[str] = field(default_factory=list)
    mitigation: str | None = None
    limitations: list[str] = field(
        default_factory=lambda: [
            "risk_signals_are_static_heuristics",
            "candidates_are_not_verified",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_type": _enum_value(self.risk_type),
            "severity": _enum_value(self.severity),
            "description": self.description,
            "source": self.source,
            "affected_artifact": self.affected_artifact,
            "affected_resource": self.affected_resource,
            "evidence_ids": list(self.evidence_ids),
            "constraint_ids": list(self.constraint_ids),
            "mitigation": self.mitigation,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class CounterfactualRemediationCandidate:
    """Hypothesis-conditional remediation candidate (never verified/applied in Part 1)."""

    id: str
    remediation_run_id: str
    organization_id: str
    project_id: str
    incident_id: str
    analysis_id: str
    hypothesis_id: str
    candidate_key: str = ""
    title: str = ""
    summary: str = ""
    artifact_type: RemediationArtifactType | str | None = None
    affected_artifact_ids: list[str] = field(default_factory=list)
    primary_artifact_id: str | None = None
    target_paths: list[str] = field(default_factory=list)
    change_types: list[CounterfactualChangeType | str] = field(default_factory=list)
    changes: list[CounterfactualChange] = field(default_factory=list)
    current_state_snapshot: RemediationCurrentState | dict[str, Any] | None = None
    counterfactual_state_snapshot: RemediationCounterfactualState | dict[str, Any] | None = None
    expected_effects: list[str] = field(default_factory=list)
    expected_preserved_behaviors: list[str] = field(default_factory=list)
    expected_failure_condition: str | CounterfactualFailureCondition | None = None
    assumptions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=lambda: list(_DEFAULT_CANDIDATE_LIMITATIONS))
    constraints: list[RemediationConstraint] = field(default_factory=list)
    unsatisfied_constraints: list[RemediationConstraint] = field(default_factory=list)
    verification_requirements: list[RemediationVerificationRequirement] = field(
        default_factory=list
    )
    rollback_plan: RemediationRollbackPlan | dict[str, Any] | None = None
    risk_summary: list[RemediationRiskSignal] | list[dict[str, Any]] = field(default_factory=list)
    blast_radius_summary: dict[str, Any] = field(default_factory=dict)
    generator_type: str | None = None
    generator_name: str | None = None
    generator_version: str | None = None
    template_id: str | None = None
    template_version: str | None = None
    status: CounterfactualCandidateStatus = CounterfactualCandidateStatus.DRAFT
    # Phase 6A.6 Part 2 generation metadata (unverified candidates only).
    rendered_patch: str | None = None
    patch_format: str | None = None
    patch_hash: str | None = None
    changed_file_count: int = 0
    changed_line_count: int = 0
    risk_score: float | None = None
    risk_level: str | None = None
    blast_radius: str | None = None
    priority_score: float | None = None
    priority_status: str | None = None
    deduplication_fingerprint: str | None = None
    validation_status: str | None = None
    constraint_status: str | None = None
    prompt_version: str | None = None
    side_effects_json: list[Any] = field(default_factory=list)
    quality_components_json: dict[str, Any] = field(default_factory=dict)
    risk_components_json: dict[str, Any] = field(default_factory=dict)
    generation_provenance: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        failure = self.expected_failure_condition
        risk_out: list[Any] = []
        for item in self.risk_summary:
            risk_out.append(_maybe_to_dict(item) if not isinstance(item, dict) else dict(item))
        return {
            "id": self.id,
            "remediation_run_id": self.remediation_run_id,
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "incident_id": self.incident_id,
            "analysis_id": self.analysis_id,
            "hypothesis_id": self.hypothesis_id,
            "candidate_key": self.candidate_key,
            "title": self.title,
            "summary": self.summary,
            "artifact_type": _enum_value(self.artifact_type),
            "affected_artifact_ids": list(self.affected_artifact_ids),
            "primary_artifact_id": self.primary_artifact_id,
            "target_paths": list(self.target_paths),
            "change_types": [_enum_value(t) for t in self.change_types],
            "changes": _list_to_dict(self.changes),
            "current_state_snapshot": (
                dict(self.current_state_snapshot)
                if isinstance(self.current_state_snapshot, dict)
                else _maybe_to_dict(self.current_state_snapshot)
            ),
            "counterfactual_state_snapshot": (
                dict(self.counterfactual_state_snapshot)
                if isinstance(self.counterfactual_state_snapshot, dict)
                else _maybe_to_dict(self.counterfactual_state_snapshot)
            ),
            "expected_effects": list(self.expected_effects),
            "expected_preserved_behaviors": list(self.expected_preserved_behaviors),
            "expected_failure_condition": (
                failure if isinstance(failure, str) or failure is None else _maybe_to_dict(failure)
            ),
            "assumptions": list(self.assumptions),
            "limitations": list(self.limitations),
            "constraints": _list_to_dict(self.constraints),
            "unsatisfied_constraints": _list_to_dict(self.unsatisfied_constraints),
            "verification_requirements": _list_to_dict(self.verification_requirements),
            "rollback_plan": (
                dict(self.rollback_plan)
                if isinstance(self.rollback_plan, dict)
                else _maybe_to_dict(self.rollback_plan)
            ),
            "risk_summary": risk_out,
            "blast_radius_summary": dict(self.blast_radius_summary),
            "generator_type": self.generator_type,
            "generator_name": self.generator_name,
            "generator_version": self.generator_version,
            "template_id": self.template_id,
            "template_version": self.template_version,
            "status": _enum_value(self.status),
            "rendered_patch": self.rendered_patch,
            "patch_format": self.patch_format,
            "patch_hash": self.patch_hash,
            "changed_file_count": self.changed_file_count,
            "changed_line_count": self.changed_line_count,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "blast_radius": self.blast_radius,
            "priority_score": self.priority_score,
            "priority_status": self.priority_status,
            "deduplication_fingerprint": self.deduplication_fingerprint,
            "validation_status": self.validation_status,
            "constraint_status": self.constraint_status,
            "prompt_version": self.prompt_version,
            "side_effects_json": list(self.side_effects_json),
            "quality_components_json": dict(self.quality_components_json),
            "risk_components_json": dict(self.risk_components_json),
            "generation_provenance": dict(self.generation_provenance),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(slots=True)
class HypothesisEligibilityResult:
    """Deterministic eligibility decision for counterfactual remediation planning."""

    status: HypothesisEligibilityStatus
    hypothesis_id: str | None = None
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    missing_prerequisites: list[str] = field(default_factory=list)
    input_snapshot: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(
        default_factory=lambda: [
            "eligibility_is_not_verification",
            "candidates_are_not_verified",
            "eligible_hypotheses_remain_conditional",
        ]
    )
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": _enum_value(self.status),
            "hypothesis_id": self.hypothesis_id,
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "blocking_reasons": list(self.blocking_reasons),
            "missing_prerequisites": list(self.missing_prerequisites),
            "input_snapshot": dict(self.input_snapshot),
            "limitations": list(self.limitations),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class CandidateStructuralValidationResult:
    """Structural validation only — not independent verification."""

    status: CandidateStructuralValidationStatus
    candidate_id: str | None = None
    hypothesis_id: str | None = None
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    checks: dict[str, bool | str] = field(default_factory=dict)
    validator_version: str = REMEDIATION_CANDIDATE_VALIDATOR_VERSION
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
            "hypothesis_id": self.hypothesis_id,
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "blocking_issues": list(self.blocking_issues),
            "checks": dict(self.checks),
            "validator_version": self.validator_version,
            "limitations": list(self.limitations),
            "created_at": self.created_at.isoformat(),
        }
