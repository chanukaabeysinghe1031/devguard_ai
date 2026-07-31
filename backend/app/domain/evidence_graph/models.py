"""Phase 6A.2 evidence graph domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.evidence_graph.enums import (
    EvidenceGraphStatus,
    GraphConsistencyStatus,
    GraphDerivationType,
    GraphEdgeType,
    GraphNodeType,
)


@dataclass(slots=False, frozen=False)
class EvidenceGraphNode:
    id: str
    analysis_id: str
    organization_id: str
    project_id: str | None
    node_type: GraphNodeType
    label: str
    stable_key: str
    artifact_id: str | None = None
    parser_entity_id: str | None = None
    source_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    extraction_method: str = "parser"
    confidence: float = 1.0
    created_at: datetime | None = None


@dataclass(slots=False, frozen=False)
class EvidenceGraphEdge:
    id: str
    analysis_id: str
    organization_id: str
    source_node_id: str
    target_node_id: str
    edge_type: GraphEdgeType
    stable_key: str
    evidence_ids: list[str] = field(default_factory=list)
    derivation_type: GraphDerivationType = GraphDerivationType.PARSER_DETERMINISTIC
    confidence: float = 1.0
    explanation: str | None = None
    rule_id: str | None = None
    rule_version: str | None = None
    created_at: datetime | None = None


@dataclass(slots=False, frozen=False)
class GraphQualityMetrics:
    node_count: int = 0
    edge_count: int = 0
    node_counts_by_type: dict[str, int] = field(default_factory=dict)
    edge_counts_by_type: dict[str, int] = field(default_factory=dict)
    deterministic_edge_ratio: float = 0.0
    inferred_edge_ratio: float = 0.0
    source_artifact_coverage: float = 0.0
    orphan_node_ratio: float = 0.0
    cross_artifact_link_count: int = 0
    temporal_link_count: int = 0
    consistency_score: float | None = None
    graph_construction_duration_ms: int | None = None
    missing_link_count: int = 0
    truncated: bool = False


@dataclass(slots=False, frozen=False)
class GraphConsistencyRuleResult:
    rule_id: str
    rule_version: str
    passed: bool
    severity: str = "error"
    message: str = ""
    related_node_ids: list[str] = field(default_factory=list)
    related_edge_ids: list[str] = field(default_factory=list)


@dataclass(slots=False, frozen=False)
class GraphConsistencyReport:
    status: GraphConsistencyStatus
    valid_node_count: int = 0
    valid_edge_count: int = 0
    invalid_edge_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    orphan_nodes: list[str] = field(default_factory=list)
    missing_expected_links: list[str] = field(default_factory=list)
    conflicting_links: list[str] = field(default_factory=list)
    consistency_score: float = 0.0
    rule_results: list[GraphConsistencyRuleResult] = field(default_factory=list)


@dataclass(slots=False, frozen=False)
class EvidenceGraph:
    id: str
    analysis_id: str
    organization_id: str
    project_id: str | None
    incident_id: str | None
    artifact_bundle_id: str | None
    status: EvidenceGraphStatus
    nodes: list[EvidenceGraphNode] = field(default_factory=list)
    edges: list[EvidenceGraphEdge] = field(default_factory=list)
    metrics: GraphQualityMetrics = field(default_factory=GraphQualityMetrics)
    consistency: GraphConsistencyReport | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    missing_link_diagnostics: list[str] = field(default_factory=list)
    builder_version: str = "evidence_graph_v1"
