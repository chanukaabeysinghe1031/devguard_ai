"""Domain contracts for hypothesis-directed retrieval (Phase 6A.5 Part 1B)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.hypothesis_retrieval.enums import (
    HypothesisRetrievalRunStatus,
    HypothesisRetrievalSessionStatus,
    HypothesisRetrievalSourceType,
    RetrievalExecutionMode,
    RetrievalFailureType,
    RetrievalItemRelation,
    RetrievalQueryType,
)

CONTEXT_VERSION = "retrieval_context_v1"
PLAN_VERSION = "retrieval_plan_v1"
RETRIEVAL_PIPELINE_VERSION = "hypothesis_directed_v1"
TRUNCATION_RULE_VERSION = "truncation_v1"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class HypothesisRetrievalQuerySpec:
    query_id: str
    query_type: RetrievalQueryType
    query_text: str
    normalized_query: str
    source_types: list[HypothesisRetrievalSourceType] = field(default_factory=list)
    target_category: str | None = None
    target_artifact_types: list[str] = field(default_factory=list)
    target_paths: list[str] = field(default_factory=list)
    target_resource_identifiers: list[str] = field(default_factory=list)
    target_actions: list[str] = field(default_factory=list)
    graph_node_ids: list[str] = field(default_factory=list)
    expected_relation: RetrievalItemRelation = RetrievalItemRelation.UNKNOWN
    top_k: int = 10
    priority: int = 100
    reason: str = ""
    originating_rule_id: str | None = None
    originating_hypothesis_field: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query_type": self.query_type.value,
            "query_text": self.query_text,
            "normalized_query": self.normalized_query,
            "source_types": [s.value for s in self.source_types],
            "target_category": self.target_category,
            "target_artifact_types": list(self.target_artifact_types),
            "target_paths": list(self.target_paths),
            "target_resource_identifiers": list(self.target_resource_identifiers),
            "target_actions": list(self.target_actions),
            "graph_node_ids": list(self.graph_node_ids),
            "expected_relation": self.expected_relation.value,
            "top_k": self.top_k,
            "priority": self.priority,
            "reason": self.reason,
            "originating_rule_id": self.originating_rule_id,
            "originating_hypothesis_field": self.originating_hypothesis_field,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class HypothesisRetrievalPlan:
    hypothesis_id: str
    session_id: str | None = None
    execution_mode: RetrievalExecutionMode = RetrievalExecutionMode.MULTI_QUERY
    plan_version: str = PLAN_VERSION
    query_specs: list[HypothesisRetrievalQuerySpec] = field(default_factory=list)
    enabled_source_types: list[HypothesisRetrievalSourceType] = field(default_factory=list)
    excluded_source_types: list[HypothesisRetrievalSourceType] = field(default_factory=list)
    graph_constraints: dict[str, Any] = field(default_factory=dict)
    artifact_constraints: dict[str, Any] = field(default_factory=dict)
    repository_constraints: dict[str, Any] = field(default_factory=dict)
    time_constraints: dict[str, Any] = field(default_factory=dict)
    result_limits: dict[str, int] = field(default_factory=dict)
    timeout_seconds: float = 45.0
    cache_policy: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utc_now)
    plan_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_key": self.plan_key,
            "hypothesis_id": self.hypothesis_id,
            "session_id": self.session_id,
            "execution_mode": self.execution_mode.value,
            "plan_version": self.plan_version,
            "query_specs": [q.to_dict() for q in self.query_specs],
            "enabled_source_types": [s.value for s in self.enabled_source_types],
            "excluded_source_types": [s.value for s in self.excluded_source_types],
            "graph_constraints": dict(self.graph_constraints),
            "artifact_constraints": dict(self.artifact_constraints),
            "repository_constraints": dict(self.repository_constraints),
            "time_constraints": dict(self.time_constraints),
            "result_limits": dict(self.result_limits),
            "timeout_seconds": self.timeout_seconds,
            "cache_policy": dict(self.cache_policy),
            "warnings": list(self.warnings),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class HypothesisRetrievalContext:
    analysis_id: str
    organization_id: str
    incident_id: str | None
    hypothesis_id: str
    hypothesis_key: str
    project_id: str | None = None
    category_code: str | None = None
    level_1_code: str | None = None
    level_2_code: str | None = None
    level_3_code: str | None = None
    title: str = ""
    causal_claim: str = ""
    expected_observations: list[str] = field(default_factory=list)
    falsifying_observations: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    proposed_verification_steps: list[str] = field(default_factory=list)
    generation_prior_score: float = 0.0
    critic_decision: str | None = None
    hypothesis_status: str | None = None
    temporal_primary_summary: str | None = None
    temporal_primary_event_id: str | None = None
    upstream_event_summaries: list[str] = field(default_factory=list)
    downstream_symptom_summaries: list[str] = field(default_factory=list)
    temporal_confidence: float | None = None
    temporal_warnings: list[str] = field(default_factory=list)
    root_cause_node_id: str | None = None
    observed_failure_node_id: str | None = None
    causal_path_node_ids: list[str] = field(default_factory=list)
    causal_path_edge_ids: list[str] = field(default_factory=list)
    graph_neighborhood_nodes: list[dict[str, Any]] = field(default_factory=list)
    graph_neighborhood_edges: list[dict[str, Any]] = field(default_factory=list)
    graph_consistency_status: str | None = None
    graph_warnings: list[str] = field(default_factory=list)
    missing_graph_links: list[str] = field(default_factory=list)
    affected_artifact_id: str | None = None
    affected_path: str | None = None
    related_artifacts: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    parser_evidence: list[dict[str, Any]] = field(default_factory=list)
    artifact_availability: list[str] = field(default_factory=list)
    missing_artifacts: list[str] = field(default_factory=list)
    open_set_status: str | None = None
    disagreement_status: str | None = None
    classification_candidates: list[dict[str, Any]] = field(default_factory=list)
    commit_sha: str | None = None
    workflow_path: str | None = None
    secret_redaction_status: str = "applied"
    excluded_sensitive_fields: list[str] = field(default_factory=list)
    context_version: str = CONTEXT_VERSION
    total_character_count: int = 0
    was_truncated: bool = False
    original_size: int = 0
    final_size: int = 0
    truncated_sections: list[str] = field(default_factory=list)
    truncation_rule_version: str = TRUNCATION_RULE_VERSION
    truncation_reasons: list[str] = field(default_factory=list)
    source_counts: dict[str, int] = field(default_factory=dict)
    combined_text_excerpt: str = ""
    error_signature: str | None = None
    permission_actions: list[str] = field(default_factory=list)
    resource_identifiers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HypothesisRetrievedItem:
    source_type: HypothesisRetrievalSourceType
    source_system: str
    text_excerpt: str
    query_id: str
    hypothesis_id: str
    session_id: str | None = None
    source_id: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    artifact_id: str | None = None
    graph_node_id: str | None = None
    graph_edge_id: str | None = None
    temporal_event_id: str | None = None
    historical_incident_id: str | None = None
    title: str | None = None
    normalized_text_hash: str | None = None
    source_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    repository: str | None = None
    commit_sha: str | None = None
    source_timestamp: str | None = None
    retrieval_score: float = 0.0
    lexical_score: float | None = None
    vector_score: float | None = None
    historical_score: float | None = None
    graph_distance: float | None = None
    adapter_name: str = ""
    adapter_version: str = "v1"
    embedding_model_version: str | None = None
    relation_candidate: RetrievalItemRelation = RetrievalItemRelation.UNKNOWN
    rank_within_query: int = 0
    global_session_order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    redaction_status: str = "masked"
    associated_query_ids: list[str] = field(default_factory=list)
    contributing_adapters: list[str] = field(default_factory=list)
    id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_type"] = self.source_type.value
        data["relation_candidate"] = self.relation_candidate.value
        return data


@dataclass(slots=True)
class HypothesisRetrievalAdapterResult:
    adapter_name: str
    adapter_version: str
    source_type: HypothesisRetrievalSourceType
    query_id: str
    status: str
    raw_result_count: int = 0
    items: list[HypothesisRetrievedItem] = field(default_factory=list)
    duration_ms: int | None = None
    cache_hit: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    failure_type: RetrievalFailureType | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "source_type": self.source_type.value,
            "query_id": self.query_id,
            "status": self.status,
            "raw_result_count": self.raw_result_count,
            "items": [i.to_dict() for i in self.items],
            "duration_ms": self.duration_ms,
            "cache_hit": self.cache_hit,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "failure_type": self.failure_type.value if self.failure_type else None,
        }


@dataclass(slots=True)
class HypothesisRetrievalQueryExecution:
    query_id: str
    query_type: RetrievalQueryType
    normalized_query: str
    source_types: list[HypothesisRetrievalSourceType] = field(default_factory=list)
    status: str = "PENDING"
    adapters_attempted: list[str] = field(default_factory=list)
    adapters_succeeded: list[str] = field(default_factory=list)
    raw_result_count: int = 0
    accepted_result_count: int = 0
    cache_hit: bool = False
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    failure_type: RetrievalFailureType | None = None
    warnings: list[str] = field(default_factory=list)
    error_summary: str | None = None
    session_id: str | None = None
    id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "query_id": self.query_id,
            "query_type": self.query_type.value,
            "normalized_query": self.normalized_query,
            "source_types": [s.value for s in self.source_types],
            "status": self.status,
            "adapters_attempted": list(self.adapters_attempted),
            "adapters_succeeded": list(self.adapters_succeeded),
            "raw_result_count": self.raw_result_count,
            "accepted_result_count": self.accepted_result_count,
            "cache_hit": self.cache_hit,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "failure_type": self.failure_type.value if self.failure_type else None,
            "warnings": list(self.warnings),
            "error_summary": self.error_summary,
        }


@dataclass(slots=True)
class HypothesisRetrievalSession:
    organization_id: str
    analysis_id: str
    hypothesis_id: str
    hypothesis_key: str
    retrieval_run_id: str | None = None
    project_id: str | None = None
    incident_id: str | None = None
    status: HypothesisRetrievalSessionStatus = HypothesisRetrievalSessionStatus.PENDING
    execution_mode: RetrievalExecutionMode = RetrievalExecutionMode.MULTI_QUERY
    retrieval_context_version: str = CONTEXT_VERSION
    retrieval_plan_version: str = PLAN_VERSION
    hypothesis_prior_score_snapshot: float = 0.0
    category_code: str | None = None
    causal_claim_snapshot: str = ""
    affected_artifact_id: str | None = None
    root_cause_node_id: str | None = None
    observed_failure_node_id: str | None = None
    query_count: int = 0
    raw_result_count: int = 0
    accepted_result_count: int = 0
    unique_source_count: int = 0
    cache_hit_count: int = 0
    source_types_attempted: list[str] = field(default_factory=list)
    source_types_succeeded: list[str] = field(default_factory=list)
    source_types_unavailable: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    context: HypothesisRetrievalContext | None = None
    plan: HypothesisRetrievalPlan | None = None
    query_executions: list[HypothesisRetrievalQueryExecution] = field(default_factory=list)
    items: list[HypothesisRetrievedItem] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "retrieval_run_id": self.retrieval_run_id,
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "incident_id": self.incident_id,
            "analysis_id": self.analysis_id,
            "hypothesis_id": self.hypothesis_id,
            "hypothesis_key": self.hypothesis_key,
            "status": self.status.value,
            "execution_mode": self.execution_mode.value,
            "retrieval_context_version": self.retrieval_context_version,
            "retrieval_plan_version": self.retrieval_plan_version,
            "hypothesis_prior_score_snapshot": self.hypothesis_prior_score_snapshot,
            "category_code": self.category_code,
            "causal_claim_snapshot": self.causal_claim_snapshot,
            "affected_artifact_id": self.affected_artifact_id,
            "root_cause_node_id": self.root_cause_node_id,
            "observed_failure_node_id": self.observed_failure_node_id,
            "query_count": self.query_count,
            "raw_result_count": self.raw_result_count,
            "accepted_result_count": self.accepted_result_count,
            "unique_source_count": self.unique_source_count,
            "cache_hit_count": self.cache_hit_count,
            "source_types_attempted": list(self.source_types_attempted),
            "source_types_succeeded": list(self.source_types_succeeded),
            "source_types_unavailable": list(self.source_types_unavailable),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "metrics": dict(self.metrics),
        }


@dataclass(slots=True)
class HypothesisRetrievalRun:
    organization_id: str
    analysis_id: str
    hypothesis_generation_run_id: str | None = None
    project_id: str | None = None
    incident_id: str | None = None
    status: HypothesisRetrievalRunStatus = HypothesisRetrievalRunStatus.PENDING
    execution_mode: RetrievalExecutionMode = RetrievalExecutionMode.MULTI_QUERY
    hypothesis_count_requested: int = 0
    hypothesis_count_processed: int = 0
    session_count_complete: int = 0
    session_count_partial: int = 0
    session_count_failed: int = 0
    total_query_count: int = 0
    total_result_count: int = 0
    total_unique_source_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    configuration_snapshot: dict[str, Any] = field(default_factory=dict)
    embedding_model_version: str | None = None
    retrieval_pipeline_version: str = RETRIEVAL_PIPELINE_VERSION
    error_summary: str | None = None
    warnings: list[str] = field(default_factory=list)
    sessions: list[HypothesisRetrievalSession] = field(default_factory=list)
    id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "incident_id": self.incident_id,
            "analysis_id": self.analysis_id,
            "hypothesis_generation_run_id": self.hypothesis_generation_run_id,
            "status": self.status.value,
            "execution_mode": self.execution_mode.value,
            "hypothesis_count_requested": self.hypothesis_count_requested,
            "hypothesis_count_processed": self.hypothesis_count_processed,
            "session_count_complete": self.session_count_complete,
            "session_count_partial": self.session_count_partial,
            "session_count_failed": self.session_count_failed,
            "total_query_count": self.total_query_count,
            "total_result_count": self.total_result_count,
            "total_unique_source_count": self.total_unique_source_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "configuration_snapshot": dict(self.configuration_snapshot),
            "embedding_model_version": self.embedding_model_version,
            "retrieval_pipeline_version": self.retrieval_pipeline_version,
            "error_summary": self.error_summary,
            "warnings": list(self.warnings),
            "sessions": [s.to_dict() for s in self.sessions],
        }
