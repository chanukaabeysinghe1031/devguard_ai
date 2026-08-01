"""Minimal domain-shaped stubs used only when domain models are not yet present.

Prefer `app.domain.counterfactual_remediation.models` via `model_types`.
These stubs mirror brief §9–§34 field names so the AI package can land in parallel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

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
    RemediationVerificationStatus,
    RollbackType,
    VerifierType,
)
from app.domain.counterfactual_remediation.versions import (
    CONSTRAINT_EXTRACTOR_VERSION,
    COUNTERFACTUAL_CONTEXT_VERSION,
    COUNTERFACTUAL_STATE_VERSION,
    MINIMAL_CHANGE_PLANNER_VERSION,
    REMEDIATION_CANDIDATE_VALIDATOR_VERSION,
    REMEDIATION_CONSTRAINTS_VERSION,
    REMEDIATION_CURRENT_STATE_VERSION,
    REMEDIATION_TEMPLATES_VERSION,
)

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


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return str(uuid4())


@dataclass(slots=True)
class CounterfactualRemediationContext:
    organization_id: str = ""
    project_id: str | None = None
    incident_id: str | None = None
    analysis_id: str = ""
    hypothesis_id: str = ""
    hypothesis_key: str = ""
    hypothesis_category: str = ""
    causal_claim: str = ""
    eligibility_status: str = ""
    ranking_score: float | None = None
    candidate_selection_status: str | None = None
    support_assessment: dict[str, Any] = field(default_factory=dict)
    contradiction_assessment: dict[str, Any] = field(default_factory=dict)
    evidence_sufficiency: dict[str, Any] = field(default_factory=dict)
    critic_result: dict[str, Any] = field(default_factory=dict)
    observed_failure_node: str | None = None
    primary_temporal_event: str | None = None
    failure_signature: str | None = None
    error_code: str | None = None
    failed_workflow_job_step: str | None = None
    affected_command: str | None = None
    affected_resource: str | None = None
    failure_condition_summary: str | None = None
    downstream_symptoms: list[str] = field(default_factory=list)
    root_cause_node: str | None = None
    causal_path_nodes: list[dict[str, Any]] = field(default_factory=list)
    causal_path_edges: list[dict[str, Any]] = field(default_factory=list)
    related_artifact_nodes: list[dict[str, Any]] = field(default_factory=list)
    related_policy_nodes: list[dict[str, Any]] = field(default_factory=list)
    related_resource_nodes: list[dict[str, Any]] = field(default_factory=list)
    graph_consistency_status: str | None = None
    graph_warnings: list[str] = field(default_factory=list)
    missing_graph_links: list[str] = field(default_factory=list)
    affected_artifact: dict[str, Any] | None = None
    source_path: str | None = None
    line_range: dict[str, Any] | None = None
    parser_entities: list[dict[str, Any]] = field(default_factory=list)
    current_configuration_fragment: str | None = None
    related_changed_files: list[str] = field(default_factory=list)
    previous_successful_version: str | None = None
    artifact_quality: float | None = None
    missing_artifacts: list[str] = field(default_factory=list)
    retrieval_evidence: list[dict[str, Any]] = field(default_factory=list)
    official_constraints: list[dict[str, Any]] = field(default_factory=list)
    open_set_status: str | None = None
    classifier_disagreement: dict[str, Any] | None = None
    redaction_status: str = "masked"
    excluded_sensitive_fields: list[str] = field(default_factory=list)
    prompt_injection_warnings: list[str] = field(default_factory=list)
    context_version: str = COUNTERFACTUAL_CONTEXT_VERSION
    size_chars: int = 0
    truncation_details: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    assumptions_allowed: list[str] = field(default_factory=list)
    assumptions_prohibited: list[str] = field(default_factory=list)
    completeness: str = "COMPLETE"
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "context_is_not_verified_root_cause",
            "candidates_are_not_verified_fixes",
        ]
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "incident_id": self.incident_id,
            "analysis_id": self.analysis_id,
            "hypothesis_id": self.hypothesis_id,
            "hypothesis_key": self.hypothesis_key,
            "hypothesis_category": self.hypothesis_category,
            "causal_claim": self.causal_claim,
            "eligibility_status": self.eligibility_status,
            "ranking_score": self.ranking_score,
            "candidate_selection_status": self.candidate_selection_status,
            "completeness": self.completeness,
            "missing_artifacts": list(self.missing_artifacts),
            "missing_information": list(self.missing_information),
            "context_version": self.context_version,
            "size_chars": self.size_chars,
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class RemediationCurrentState:
    artifact_id: str | None = None
    artifact_type: RemediationArtifactType | str = RemediationArtifactType.UNKNOWN
    source_path: str | None = None
    commit_sha: str | None = None
    content_hash: str | None = None
    source_fragment: str | None = None
    structured_entities: list[dict[str, Any]] = field(default_factory=list)
    structured_relationships: list[dict[str, Any]] = field(default_factory=list)
    current_values: dict[str, Any] = field(default_factory=dict)
    current_references: list[str] = field(default_factory=list)
    current_dependencies: list[str] = field(default_factory=list)
    current_permissions: dict[str, Any] = field(default_factory=dict)
    current_conditions: list[str] = field(default_factory=list)
    current_region: str | None = None
    current_account_context: str | None = None
    current_environment: str | None = None
    current_versions: dict[str, str] = field(default_factory=dict)
    current_security_findings: list[str] = field(default_factory=list)
    current_plan_changes: list[dict[str, Any]] = field(default_factory=list)
    current_failure_condition: str | None = None
    parser_version: str | None = None
    extraction_quality: float | None = None
    missing_fields: list[str] = field(default_factory=list)
    redaction_status: str = "masked"
    state_version: str = REMEDIATION_CURRENT_STATE_VERSION
    limitations: list[str] = field(
        default_factory=lambda: ["current_state_is_bounded_snapshot_not_full_config"]
    )

    def to_dict(self) -> dict[str, Any]:
        artifact_type = self.artifact_type
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": (
                artifact_type.value if hasattr(artifact_type, "value") else artifact_type
            ),
            "source_path": self.source_path,
            "commit_sha": self.commit_sha,
            "content_hash": self.content_hash,
            "source_fragment": self.source_fragment,
            "structured_entities": list(self.structured_entities),
            "structured_relationships": list(self.structured_relationships),
            "current_values": dict(self.current_values),
            "current_references": list(self.current_references),
            "current_dependencies": list(self.current_dependencies),
            "current_permissions": dict(self.current_permissions),
            "current_conditions": list(self.current_conditions),
            "current_region": self.current_region,
            "current_account_context": self.current_account_context,
            "current_environment": self.current_environment,
            "current_versions": dict(self.current_versions),
            "missing_fields": list(self.missing_fields),
            "redaction_status": self.redaction_status,
            "state_version": self.state_version,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class RemediationCounterfactualState:
    candidate_id: str | None = None
    artifact_id: str | None = None
    artifact_type: RemediationArtifactType | str = RemediationArtifactType.UNKNOWN
    proposed_values: dict[str, Any] = field(default_factory=dict)
    proposed_references: list[str] = field(default_factory=list)
    proposed_dependencies: list[str] = field(default_factory=list)
    proposed_permissions: dict[str, Any] = field(default_factory=dict)
    proposed_conditions: list[str] = field(default_factory=list)
    proposed_region: str | None = None
    proposed_environment: str | None = None
    proposed_versions: dict[str, str] = field(default_factory=dict)
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
    limitations: list[str] = field(
        default_factory=lambda: [
            "counterfactual_state_is_hypothetical",
            "not_verified_as_fix",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "artifact_id": self.artifact_id,
            "expected_failure_condition_status": self.expected_failure_condition_status.value,
            "proposed_values": dict(self.proposed_values),
            "assumptions": list(self.assumptions),
            "unknown_effects": list(self.unknown_effects),
            "state_version": self.state_version,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class CounterfactualChange:
    id: str = field(default_factory=_new_id)
    candidate_id: str | None = None
    artifact_id: str | None = None
    artifact_type: RemediationArtifactType | str = RemediationArtifactType.UNKNOWN
    source_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    change_type: CounterfactualChangeType = CounterfactualChangeType.UNKNOWN
    target_entity_id: str | None = None
    target_property: str | None = None
    original_fragment: str | None = None
    proposed_fragment: str | None = None
    normalized_diff: str | None = None
    expected_effect: str | None = None
    expected_failure_condition_removed: bool = False
    rationale: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    graph_node_ids: list[str] = field(default_factory=list)
    graph_edge_ids: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    change_order: int = 0
    content_hash_before: str | None = None
    content_hash_after_candidate: str | None = None
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "change_type": self.change_type.value,
            "target_property": self.target_property,
            "change_order": self.change_order,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class RemediationConstraint:
    id: str = field(default_factory=_new_id)
    organization_id: str = ""
    project_id: str | None = None
    incident_id: str | None = None
    analysis_id: str = ""
    hypothesis_id: str = ""
    candidate_id: str | None = None
    constraint_key: str = ""
    constraint_type: ConstraintType = ConstraintType.EVIDENCE_LIMITATION
    severity: ConstraintSeverity = ConstraintSeverity.MEDIUM
    source_type: ConstraintSourceType = ConstraintSourceType.UNKNOWN
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
    confidence: float = 1.0
    extraction_method: str = "deterministic"
    extractor_version: str = CONSTRAINT_EXTRACTOR_VERSION
    is_blocking: bool = False
    is_satisfied: bool | None = None
    satisfaction_status: ConstraintSatisfactionStatus = (
        ConstraintSatisfactionStatus.NOT_EVALUATED
    )
    limitations: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "constraint_key": self.constraint_key,
            "constraint_type": self.constraint_type.value,
            "severity": self.severity.value,
            "source_type": self.source_type.value,
            "description": self.description,
            "machine_readable_rule": dict(self.machine_readable_rule),
            "is_blocking": self.is_blocking,
            "satisfaction_status": self.satisfaction_status.value,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class RemediationConstraintSet:
    hypothesis_id: str = ""
    candidate_id: str | None = None
    constraints: list[RemediationConstraint] = field(default_factory=list)
    blocking_constraints: list[RemediationConstraint] = field(default_factory=list)
    security_constraints: list[RemediationConstraint] = field(default_factory=list)
    workflow_constraints: list[RemediationConstraint] = field(default_factory=list)
    terraform_constraints: list[RemediationConstraint] = field(default_factory=list)
    cloud_constraints: list[RemediationConstraint] = field(default_factory=list)
    repository_constraints: list[RemediationConstraint] = field(default_factory=list)
    operational_constraints: list[RemediationConstraint] = field(default_factory=list)
    missing_constraint_sources: list[str] = field(default_factory=list)
    extraction_warnings: list[str] = field(default_factory=list)
    extraction_errors: list[str] = field(default_factory=list)
    extraction_version: str = REMEDIATION_CONSTRAINTS_VERSION
    completeness: ConstraintSetCompleteness = ConstraintSetCompleteness.PARTIAL
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "candidate_id": self.candidate_id,
            "constraints": [c.to_dict() for c in self.constraints],
            "blocking_count": len(self.blocking_constraints),
            "missing_constraint_sources": list(self.missing_constraint_sources),
            "extraction_warnings": list(self.extraction_warnings),
            "extraction_errors": list(self.extraction_errors),
            "extraction_version": self.extraction_version,
            "completeness": self.completeness.value,
        }


@dataclass(slots=True)
class ConstraintExtractionResult:
    extractor_name: str = ""
    status: ConstraintExtractionStatus = ConstraintExtractionStatus.NO_CONSTRAINTS
    constraints: list[RemediationConstraint] = field(default_factory=list)
    artifact_ids_processed: list[str] = field(default_factory=list)
    extracted_count: int = 0
    blocking_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: int = 0
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "extractor_name": self.extractor_name,
            "status": self.status.value,
            "extracted_count": self.extracted_count,
            "blocking_count": self.blocking_count,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "duration_ms": self.duration_ms,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class ConstraintConflict:
    id: str = field(default_factory=_new_id)
    conflict_type: str = ""
    involved_constraint_keys: list[str] = field(default_factory=list)
    severity: ConstraintSeverity = ConstraintSeverity.BLOCKING
    explanation: str = ""
    must_stop_generation: bool = False
    missing_evidence: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "conflict_type": self.conflict_type,
            "involved_constraint_keys": list(self.involved_constraint_keys),
            "severity": self.severity.value,
            "explanation": self.explanation,
            "must_stop_generation": self.must_stop_generation,
            "missing_evidence": list(self.missing_evidence),
        }


@dataclass(slots=True)
class CounterfactualPrecondition:
    id: str = field(default_factory=_new_id)
    hypothesis_id: str = ""
    condition_type: str = ""
    description: str = ""
    expected_current_state: str | None = None
    actual_current_state: str | None = None
    status: PreconditionStatus = PreconditionStatus.UNKNOWN
    evidence_ids: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    graph_node_ids: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    is_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "hypothesis_id": self.hypothesis_id,
            "condition_type": self.condition_type,
            "description": self.description,
            "status": self.status.value,
            "is_required": self.is_required,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class CounterfactualFailureCondition:
    condition_id: str = field(default_factory=_new_id)
    hypothesis_id: str = ""
    observed_condition: str = ""
    condition_type: str = ""
    triggering_action: str | None = None
    affected_resource: str | None = None
    active_principal: str | None = None
    affected_artifact: str | None = None
    expected_condition_after_change: str = ""
    measurable_static_indicator: str | None = None
    required_verifier_types: list[VerifierType | str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "expected_language_only_not_runtime_guarantee",
        ]
    )
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition_id": self.condition_id,
            "hypothesis_id": self.hypothesis_id,
            "observed_condition": self.observed_condition,
            "condition_type": self.condition_type,
            "expected_condition_after_change": self.expected_condition_after_change,
            "limitations": list(self.limitations),
            "confidence": self.confidence,
        }


@dataclass(slots=True)
class MinimalChangeObjective:
    hypothesis_id: str = ""
    primary_target: str | None = None
    primary_property: str | None = None
    desired_state: str | None = None
    maximum_files: int = 5
    maximum_changed_lines: int = 200
    allowed_artifact_types: list[str] = field(default_factory=list)
    prohibited_artifact_types: list[str] = field(
        default_factory=lambda: [RemediationArtifactType.SOURCE_CODE.value]
    )
    preserve_behaviors: list[str] = field(default_factory=list)
    avoid_side_effects: list[str] = field(default_factory=list)
    required_constraints: list[str] = field(default_factory=list)
    optimization_priorities: list[str] = field(
        default_factory=lambda: list(OPTIMIZATION_PRIORITIES)
    )
    objective_version: str = MINIMAL_CHANGE_PLANNER_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "primary_target": self.primary_target,
            "primary_property": self.primary_property,
            "desired_state": self.desired_state,
            "maximum_files": self.maximum_files,
            "maximum_changed_lines": self.maximum_changed_lines,
            "optimization_priorities": list(self.optimization_priorities),
            "objective_version": self.objective_version,
        }


@dataclass(slots=True)
class MinimalChangePlan:
    hypothesis_id: str = ""
    candidate_plan_key: str = ""
    target_artifacts: list[str] = field(default_factory=list)
    proposed_change_types: list[str] = field(default_factory=list)
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
    template_ids: list[str] = field(default_factory=list)
    locality_rules_applied: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "plan_skeleton_only_no_final_patch",
            "candidates_are_not_verified",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "candidate_plan_key": self.candidate_plan_key,
            "target_artifacts": list(self.target_artifacts),
            "proposed_change_types": list(self.proposed_change_types),
            "status": self.status.value,
            "incomplete_information": list(self.incomplete_information),
            "planner_version": self.planner_version,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class RemediationTemplate:
    template_id: str = ""
    template_version: str = REMEDIATION_TEMPLATES_VERSION
    category_codes: list[str] = field(default_factory=list)
    hierarchy_paths: list[str] = field(default_factory=list)
    supported_hypothesis_patterns: list[str] = field(default_factory=list)
    supported_artifact_types: list[str] = field(default_factory=list)
    required_preconditions: list[str] = field(default_factory=list)
    optional_preconditions: list[str] = field(default_factory=list)
    prohibited_conditions: list[str] = field(default_factory=list)
    required_constraints: list[str] = field(default_factory=list)
    change_type: CounterfactualChangeType = CounterfactualChangeType.UNKNOWN
    target_selector_rules: list[str] = field(default_factory=list)
    current_state_requirements: list[str] = field(default_factory=list)
    counterfactual_state_builder: str | None = None
    expected_effects: list[str] = field(default_factory=list)
    expected_preserved_behaviors: list[str] = field(default_factory=list)
    default_verification_requirements: list[str] = field(default_factory=list)
    default_rollback_strategy: RollbackType = RollbackType.RESTORE_ORIGINAL_FRAGMENT
    risk_notes: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    candidate_builder_implemented: bool = False
    family: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_version": self.template_version,
            "category_codes": list(self.category_codes),
            "supported_artifact_types": list(self.supported_artifact_types),
            "change_type": self.change_type.value,
            "candidate_builder_implemented": self.candidate_builder_implemented,
            "family": self.family,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class RemediationVerificationRequirement:
    requirement_id: str = field(default_factory=_new_id)
    candidate_id: str | None = None
    verifier_type: VerifierType = VerifierType.COUNTERFACTUAL_FAILURE_CONDITION
    required: bool = True
    reason: str = ""
    expected_check: str = ""
    expected_success_condition: str = ""
    blocking_on_failure: bool = True
    input_artifacts: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: ["verifier_not_executed_in_part_1"]
    )
    status: RemediationVerificationStatus = RemediationVerificationStatus.NOT_RUN

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "verifier_type": self.verifier_type.value,
            "required": self.required,
            "status": self.status.value,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class RemediationRollbackPlan:
    candidate_id: str | None = None
    rollback_type: RollbackType = RollbackType.NOT_AVAILABLE
    original_content_hashes: list[str] = field(default_factory=list)
    affected_artifacts: list[str] = field(default_factory=list)
    rollback_steps: list[dict[str, Any]] = field(default_factory=list)
    rollback_preconditions: list[str] = field(default_factory=list)
    rollback_limitations: list[str] = field(default_factory=list)
    rollback_risk: str | None = None
    can_restore_exactly: bool = False
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "rollback_type": self.rollback_type.value,
            "can_restore_exactly": self.can_restore_exactly,
            "rollback_steps": list(self.rollback_steps),
            "rollback_limitations": list(self.rollback_limitations),
        }


@dataclass(slots=True)
class RemediationRiskSignal:
    risk_type: RemediationRiskType = RemediationRiskType.UNKNOWN_SIDE_EFFECT
    severity: ConstraintSeverity = ConstraintSeverity.MEDIUM
    description: str = ""
    source: str = ""
    affected_artifact: str | None = None
    affected_resource: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    constraint_ids: list[str] = field(default_factory=list)
    mitigation: str | None = None
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_type": self.risk_type.value,
            "severity": self.severity.value,
            "description": self.description,
        }


@dataclass(slots=True)
class CounterfactualRemediationCandidate:
    id: str = field(default_factory=_new_id)
    remediation_run_id: str | None = None
    organization_id: str = ""
    project_id: str | None = None
    incident_id: str | None = None
    analysis_id: str = ""
    hypothesis_id: str = ""
    candidate_key: str = ""
    title: str = ""
    summary: str = ""
    artifact_type: RemediationArtifactType | str = RemediationArtifactType.UNKNOWN
    affected_artifact_ids: list[str] = field(default_factory=list)
    primary_artifact_id: str | None = None
    target_paths: list[str] = field(default_factory=list)
    change_types: list[str] = field(default_factory=list)
    changes: list[CounterfactualChange] = field(default_factory=list)
    current_state_snapshot: dict[str, Any] = field(default_factory=dict)
    counterfactual_state_snapshot: dict[str, Any] = field(default_factory=dict)
    expected_effects: list[str] = field(default_factory=list)
    expected_preserved_behaviors: list[str] = field(default_factory=list)
    expected_failure_condition: dict[str, Any] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "candidate_is_not_verified",
            "candidate_is_not_applied",
            "part_1_skeleton_only",
        ]
    )
    constraints: list[dict[str, Any]] = field(default_factory=list)
    unsatisfied_constraints: list[str] = field(default_factory=list)
    verification_requirements: list[RemediationVerificationRequirement] = field(
        default_factory=list
    )
    rollback_plan: RemediationRollbackPlan | None = None
    risk_summary: list[RemediationRiskSignal] = field(default_factory=list)
    blast_radius_summary: str | None = None
    generator_type: str = "deterministic_skeleton"
    generator_name: str = "minimal_change_planner"
    generator_version: str = MINIMAL_CHANGE_PLANNER_VERSION
    template_id: str | None = None
    template_version: str | None = None
    status: CounterfactualCandidateStatus = CounterfactualCandidateStatus.DRAFT
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "remediation_run_id": self.remediation_run_id,
            "organization_id": self.organization_id,
            "analysis_id": self.analysis_id,
            "hypothesis_id": self.hypothesis_id,
            "candidate_key": self.candidate_key,
            "title": self.title,
            "status": self.status.value,
            "template_id": self.template_id,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class HypothesisEligibilityResult:
    hypothesis_id: str = ""
    status: HypothesisEligibilityStatus = HypothesisEligibilityStatus.INELIGIBLE
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "status": self.status.value,
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class CandidateStructuralValidationResult:
    candidate_id: str | None = None
    status: CandidateStructuralValidationStatus = (
        CandidateStructuralValidationStatus.INCOMPLETE
    )
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejected_reasons: list[str] = field(default_factory=list)
    validator_version: str = REMEDIATION_CANDIDATE_VALIDATOR_VERSION
    limitations: list[str] = field(
        default_factory=lambda: ["structural_validation_is_not_independent_verification"]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "status": self.status.value,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "rejected_reasons": list(self.rejected_reasons),
            "validator_version": self.validator_version,
            "limitations": list(self.limitations),
        }


@dataclass(slots=True)
class CounterfactualRemediationRun:
    id: str = field(default_factory=_new_id)
    organization_id: str = ""
    project_id: str | None = None
    incident_id: str | None = None
    analysis_id: str = ""
    status: CounterfactualRemediationRunStatus = CounterfactualRemediationRunStatus.PENDING
    configuration_snapshot: dict[str, Any] = field(default_factory=dict)
    eligible_hypothesis_ids: list[str] = field(default_factory=list)
    candidate_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "candidates_are_not_verified",
            "no_llm_patch_generation_in_part_1",
            "no_verifier_execution_in_part_1",
        ]
    )
    duration_ms: int | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "analysis_id": self.analysis_id,
            "status": self.status.value,
            "eligible_hypothesis_ids": list(self.eligible_hypothesis_ids),
            "candidate_ids": list(self.candidate_ids),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "duration_ms": self.duration_ms,
        }
