# ruff: noqa: E501
"""Build typed EvidenceGraph from parse results + temporal localisation."""

from __future__ import annotations

import time
import uuid
from typing import Any

import structlog

from app.ai.evidence_graph.cross_artifact_rules import (
    apply_cross_artifact_rules,
    maybe_synthesize_nodes_from_text,
)
from app.ai.evidence_graph.type_mapping import (
    map_entity_type,
    map_relationship_type,
    stable_edge_key,
    stable_node_key,
)
from app.domain.artifacts.models import IncidentArtifactBundle, StructuredParseResult
from app.domain.evidence_graph.enums import (
    EvidenceGraphStatus,
    GraphDerivationType,
    GraphEdgeType,
    GraphNodeType,
)
from app.domain.evidence_graph.models import (
    EvidenceGraph,
    EvidenceGraphEdge,
    EvidenceGraphNode,
    GraphQualityMetrics,
)
from app.domain.temporal.enums import TemporalLinkType
from app.domain.temporal.models import TemporalLocalisationResult

logger = structlog.get_logger(__name__)

BUILDER_VERSION = "evidence_graph_v1"


class CrossArtifactEvidenceGraphBuilder:
    """Deterministic evidence graph construction (no LLM edges)."""

    def __init__(self, *, max_nodes: int = 2000, max_edges: int = 5000) -> None:
        self._max_nodes = max_nodes
        self._max_edges = max_edges

    def build(
        self,
        *,
        analysis_id: str,
        organization_id: str,
        project_id: str | None,
        incident_id: str | None,
        artifact_bundle_id: str | None,
        bundle: IncidentArtifactBundle | None,
        parse_by_artifact: dict[str, list[StructuredParseResult]],
        temporal: TemporalLocalisationResult | None,
        enabled: bool = True,
    ) -> EvidenceGraph:
        started = time.perf_counter()
        graph_id = str(uuid.uuid4())
        if not enabled:
            return EvidenceGraph(
                id=graph_id,
                analysis_id=analysis_id,
                organization_id=organization_id,
                project_id=project_id,
                incident_id=incident_id,
                artifact_bundle_id=artifact_bundle_id,
                status=EvidenceGraphStatus.DISABLED,
            )

        logger.info(
            "evidence_graph_build_started",
            analysis_id=analysis_id,
            organization_id=organization_id,
            artifact_bundle_id=artifact_bundle_id,
        )
        warnings: list[str] = []
        errors: list[str] = []
        missing: list[str] = []
        nodes_by_key: dict[str, EvidenceGraphNode] = {}
        edges_by_key: dict[str, EvidenceGraphEdge] = {}
        truncated = False

        try:
            # Pipeline run node
            if bundle:
                pr_key = stable_node_key(
                    artifact_id=None,
                    parser_entity_id=f"pipeline:{bundle.pipeline_run_id or analysis_id}",
                    node_type=GraphNodeType.PIPELINE_RUN,
                )
                nodes_by_key[pr_key] = EvidenceGraphNode(
                    id=str(uuid.uuid4()),
                    analysis_id=analysis_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    node_type=GraphNodeType.PIPELINE_RUN,
                    label=bundle.workflow_name or "pipeline",
                    stable_key=pr_key,
                    metadata={
                        "repository": bundle.repository,
                        "commit_sha": bundle.commit_sha,
                        "workflow_run_id": bundle.workflow_run_id,
                    },
                    extraction_method="bundle",
                    confidence=1.0,
                )

            for artifact_id, results in sorted(parse_by_artifact.items()):
                for parsed in results:
                    entity_id_to_key: dict[str, str] = {}
                    for entity in parsed.entities:
                        if len(nodes_by_key) >= self._max_nodes:
                            truncated = True
                            break
                        node_type = map_entity_type(entity.type)
                        key = stable_node_key(
                            artifact_id=artifact_id,
                            parser_entity_id=entity.id,
                            node_type=node_type,
                        )
                        if key not in nodes_by_key:
                            loc = entity.location
                            # Redact likely secret values from metadata
                            meta = _safe_metadata(entity.metadata)
                            nodes_by_key[key] = EvidenceGraphNode(
                                id=str(uuid.uuid4()),
                                analysis_id=analysis_id,
                                organization_id=organization_id,
                                project_id=project_id,
                                node_type=node_type,
                                label=(entity.label or entity.id)[:500],
                                stable_key=key,
                                artifact_id=artifact_id,
                                parser_entity_id=entity.id,
                                source_path=_safe_path(loc.path if loc else None),
                                line_start=loc.line_start if loc else None,
                                line_end=loc.line_end if loc else None,
                                metadata=meta,
                                extraction_method=parsed.parser_name,
                                confidence=float(parsed.extraction_quality or 0.8),
                            )
                        entity_id_to_key[entity.id] = key

                    for rel in parsed.relationships:
                        if len(edges_by_key) >= self._max_edges:
                            truncated = True
                            break
                        src_key = entity_id_to_key.get(rel.source_id)
                        tgt_key = entity_id_to_key.get(rel.target_id)
                        if not src_key or not tgt_key:
                            missing.append(
                                f"orphan_parser_rel:{rel.type}:{rel.source_id}->{rel.target_id}"
                            )
                            continue
                        edge_type = map_relationship_type(rel.type)
                        derivation = (
                            GraphDerivationType.PARSER_DETERMINISTIC
                            if rel.deterministic
                            else GraphDerivationType.TEMPORAL_HEURISTIC
                        )
                        if edge_type == GraphEdgeType.USES_ACTION:
                            derivation = GraphDerivationType.WORKFLOW_STRUCTURE
                        if edge_type == GraphEdgeType.DEPENDS_ON:
                            derivation = GraphDerivationType.TERRAFORM_REFERENCE
                        ekey = stable_edge_key(
                            edge_type=edge_type,
                            source_key=src_key,
                            target_key=tgt_key,
                            rule_id="parser",
                        )
                        if ekey in edges_by_key:
                            continue
                        edges_by_key[ekey] = EvidenceGraphEdge(
                            id=str(uuid.uuid4()),
                            analysis_id=analysis_id,
                            organization_id=organization_id,
                            source_node_id=nodes_by_key[src_key].id,
                            target_node_id=nodes_by_key[tgt_key].id,
                            edge_type=edge_type,
                            stable_key=ekey,
                            derivation_type=derivation,
                            confidence=float(rel.confidence),
                            explanation=rel.explanation,
                            rule_id="parser",
                            rule_version=parsed.parser_version,
                        )
                    if truncated:
                        break
                if truncated:
                    break

            # Synthesize IAM/AWS nodes from error text then apply rules
            nodes_list = list(nodes_by_key.values())
            for synth in maybe_synthesize_nodes_from_text(
                nodes_list,
                analysis_id=analysis_id,
                organization_id=organization_id,
                project_id=project_id,
            ):
                if len(nodes_by_key) >= self._max_nodes:
                    truncated = True
                    break
                if synth.stable_key not in nodes_by_key:
                    nodes_by_key[synth.stable_key] = synth

            for edge in apply_cross_artifact_rules(
                list(nodes_by_key.values()),
                analysis_id=analysis_id,
                organization_id=organization_id,
            ):
                if len(edges_by_key) >= self._max_edges:
                    truncated = True
                    break
                if edge.stable_key not in edges_by_key:
                    edges_by_key[edge.stable_key] = edge

            # Temporal links → graph edges
            if temporal and temporal.events:
                event_node_keys: dict[str, str] = {}
                for event in temporal.events:
                    if event.parser_entity_id and event.artifact_id:
                        # Prefer existing ERROR_EVENT/LOG_EVENT node
                        for key, node in nodes_by_key.items():
                            if (
                                node.artifact_id == event.artifact_id
                                and node.parser_entity_id == event.parser_entity_id
                            ):
                                event_node_keys[event.id] = key
                                break
                    if event.id in event_node_keys:
                        continue
                    if len(nodes_by_key) >= self._max_nodes:
                        truncated = True
                        break
                    ntype = (
                        GraphNodeType.ERROR_EVENT if event.is_failure else GraphNodeType.LOG_EVENT
                    )
                    key = stable_node_key(
                        artifact_id=event.artifact_id,
                        parser_entity_id=f"temporal:{event.id}",
                        node_type=ntype,
                    )
                    nodes_by_key[key] = EvidenceGraphNode(
                        id=str(uuid.uuid4()),
                        analysis_id=analysis_id,
                        organization_id=organization_id,
                        project_id=project_id,
                        node_type=ntype,
                        label=(event.message or event.event_type.value)[:500],
                        stable_key=key,
                        artifact_id=event.artifact_id,
                        parser_entity_id=event.parser_entity_id,
                        source_path=_safe_path(
                            event.source_location.path if event.source_location else None
                        ),
                        line_start=(
                            event.source_location.line_start if event.source_location else None
                        ),
                        line_end=event.source_location.line_end if event.source_location else None,
                        metadata={
                            "temporal_event_id": event.id,
                            "event_type": event.event_type.value,
                            "job_name": event.job_name,
                            "step_name": event.step_name,
                        },
                        extraction_method="temporal",
                        confidence=event.extraction_confidence,
                    )
                    event_node_keys[event.id] = key

                for link in temporal.causal_precedence_links:
                    src_key = event_node_keys.get(link.source_event_id)
                    tgt_key = event_node_keys.get(link.target_event_id)
                    if not src_key or not tgt_key:
                        continue
                    edge_type = _temporal_link_to_edge(link.link_type)
                    derivation = (
                        GraphDerivationType.TEMPORAL_HEURISTIC
                        if "HEURISTIC" in link.derivation.value
                        else GraphDerivationType.TEMPORAL_DETERMINISTIC
                    )
                    ekey = stable_edge_key(
                        edge_type=edge_type,
                        source_key=src_key,
                        target_key=tgt_key,
                        rule_id=link.rule_id,
                    )
                    if ekey in edges_by_key or len(edges_by_key) >= self._max_edges:
                        continue
                    edges_by_key[ekey] = EvidenceGraphEdge(
                        id=str(uuid.uuid4()),
                        analysis_id=analysis_id,
                        organization_id=organization_id,
                        source_node_id=nodes_by_key[src_key].id,
                        target_node_id=nodes_by_key[tgt_key].id,
                        edge_type=edge_type,
                        stable_key=ekey,
                        evidence_ids=list(link.supporting_event_ids),
                        derivation_type=derivation,
                        confidence=link.confidence,
                        explanation=link.explanation,
                        rule_id=link.rule_id,
                        rule_version=link.rule_version,
                    )

            if not parse_by_artifact:
                missing.append("no_parse_results")
                warnings.append("partial_graph_no_parse_results")

            nodes = list(nodes_by_key.values())
            edges = list(edges_by_key.values())
            duration_ms = int((time.perf_counter() - started) * 1000)
            metrics = _compute_metrics(
                nodes,
                edges,
                artifact_count=len(parse_by_artifact),
                duration_ms=duration_ms,
                missing_link_count=len(missing),
                truncated=truncated,
            )
            status = EvidenceGraphStatus.COMPLETE
            if truncated:
                status = EvidenceGraphStatus.TRUNCATED
                warnings.append("graph_truncated")
            elif missing or (bundle and bundle.missing_artifacts):
                status = EvidenceGraphStatus.PARTIAL
                if bundle:
                    missing.extend(f"missing_artifact:{k}" for k in bundle.missing_artifacts)

            graph = EvidenceGraph(
                id=graph_id,
                analysis_id=analysis_id,
                organization_id=organization_id,
                project_id=project_id,
                incident_id=incident_id,
                artifact_bundle_id=artifact_bundle_id,
                status=status,
                nodes=nodes,
                edges=edges,
                metrics=metrics,
                warnings=warnings,
                errors=errors,
                missing_link_diagnostics=missing,
                builder_version=BUILDER_VERSION,
            )
            logger.info(
                "evidence_graph_build_completed",
                analysis_id=analysis_id,
                organization_id=organization_id,
                graph_id=graph_id,
                node_count=len(nodes),
                edge_count=len(edges),
                cross_artifact_edge_count=metrics.cross_artifact_link_count,
                truncated=truncated,
                status=status.value,
                duration_ms=duration_ms,
            )
            return graph
        except Exception as exc:  # noqa: BLE001
            logger.exception("evidence_graph_build_failed", analysis_id=analysis_id)
            return EvidenceGraph(
                id=graph_id,
                analysis_id=analysis_id,
                organization_id=organization_id,
                project_id=project_id,
                incident_id=incident_id,
                artifact_bundle_id=artifact_bundle_id,
                status=EvidenceGraphStatus.FAILED,
                errors=[type(exc).__name__],
                metrics=GraphQualityMetrics(
                    graph_construction_duration_ms=int((time.perf_counter() - started) * 1000)
                ),
            )


def _temporal_link_to_edge(link_type: TemporalLinkType) -> GraphEdgeType:
    mapping = {
        TemporalLinkType.OCCURRED_BEFORE: GraphEdgeType.OCCURRED_BEFORE,
        TemporalLinkType.OCCURRED_AFTER: GraphEdgeType.OCCURRED_AFTER,
        TemporalLinkType.DOWNSTREAM_SYMPTOM_OF: GraphEdgeType.DOWNSTREAM_SYMPTOM_OF,
        TemporalLinkType.CANDIDATE_CAUSE_OF: GraphEdgeType.CANDIDATE_CAUSE_OF,
        TemporalLinkType.PARALLEL_WITH: GraphEdgeType.PARALLEL_WITH,
        TemporalLinkType.TRIGGERED_RETRY: GraphEdgeType.RETRY_OF,
        TemporalLinkType.DEPENDS_ON_JOB: GraphEdgeType.NEEDS,
    }
    return mapping.get(link_type, GraphEdgeType.OCCURRED_BEFORE)


def _safe_metadata(meta: dict[str, Any] | None) -> dict[str, Any]:
    if not meta:
        return {}
    out: dict[str, Any] = {}
    for key, value in meta.items():
        lk = str(key).lower()
        if any(s in lk for s in ("secret", "password", "token", "credential", "key")):
            out[key] = "[REDACTED]"
            continue
        if isinstance(value, str) and len(value) > 500:
            out[key] = value[:500] + "…"
        else:
            out[key] = value
    return out


def _safe_path(path: str | None) -> str | None:
    if not path:
        return None
    cleaned = path.replace("\\", "/").lstrip("/")
    if ".." in cleaned.split("/"):
        return None
    return cleaned[:500]


def _compute_metrics(
    nodes: list[EvidenceGraphNode],
    edges: list[EvidenceGraphEdge],
    *,
    artifact_count: int,
    duration_ms: int,
    missing_link_count: int,
    truncated: bool,
) -> GraphQualityMetrics:
    node_counts: dict[str, int] = {}
    for node in nodes:
        node_counts[node.node_type.value] = node_counts.get(node.node_type.value, 0) + 1
    edge_counts: dict[str, int] = {}
    det = 0
    inferred = 0
    cross = 0
    temporal = 0
    for edge in edges:
        edge_counts[edge.edge_type.value] = edge_counts.get(edge.edge_type.value, 0) + 1
        if edge.derivation_type in {
            GraphDerivationType.PARSER_DETERMINISTIC,
            GraphDerivationType.WORKFLOW_STRUCTURE,
            GraphDerivationType.TERRAFORM_REFERENCE,
            GraphDerivationType.TEMPORAL_DETERMINISTIC,
        }:
            det += 1
        else:
            inferred += 1
        if edge.derivation_type == GraphDerivationType.CROSS_ARTIFACT_RULE:
            cross += 1
        if edge.derivation_type in {
            GraphDerivationType.TEMPORAL_DETERMINISTIC,
            GraphDerivationType.TEMPORAL_HEURISTIC,
        }:
            temporal += 1

    connected = set()
    for edge in edges:
        connected.add(edge.source_node_id)
        connected.add(edge.target_node_id)
    orphans = [
        n for n in nodes if n.id not in connected and n.node_type != GraphNodeType.PIPELINE_RUN
    ]
    total = max(len(edges), 1)
    artifacts_with_nodes = len({n.artifact_id for n in nodes if n.artifact_id})
    coverage = artifacts_with_nodes / artifact_count if artifact_count else (1.0 if nodes else 0.0)
    return GraphQualityMetrics(
        node_count=len(nodes),
        edge_count=len(edges),
        node_counts_by_type=node_counts,
        edge_counts_by_type=edge_counts,
        deterministic_edge_ratio=det / total,
        inferred_edge_ratio=inferred / total,
        source_artifact_coverage=coverage,
        orphan_node_ratio=(len(orphans) / len(nodes)) if nodes else 0.0,
        cross_artifact_link_count=cross,
        temporal_link_count=temporal,
        graph_construction_duration_ms=duration_ms,
        missing_link_count=missing_link_count,
        truncated=truncated,
    )
