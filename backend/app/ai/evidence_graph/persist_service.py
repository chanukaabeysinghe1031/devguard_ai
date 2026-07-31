"""Persist Phase 6A.2 temporal localisation and evidence graph domain objects."""

from __future__ import annotations

import dataclasses
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.evidence_graph.models import EvidenceGraph, GraphConsistencyReport
from app.domain.temporal.models import TemporalLocalisationResult
from app.infrastructure.database.models.temporal_evidence_graph import (
    EvidenceGraphEdgeRow,
    EvidenceGraphNodeRow,
    EvidenceGraphRow,
    GraphConsistencyReportRow,
    TemporalEventLinkRow,
    TemporalEventRow,
    TemporalLocalisationResultRow,
)

logger = structlog.get_logger(__name__)


def _dataclass_to_dict(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _dataclass_to_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, list):
        return [_dataclass_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _dataclass_to_dict(v) for k, v in obj.items()}
    if hasattr(obj, "value"):
        try:
            return obj.value
        except Exception:  # noqa: BLE001
            return str(obj)
    return obj


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _optional_uuid(value: str | None) -> UUID | None:
    """Best-effort UUID conversion; returns ``None`` for empty/invalid input.

    Optional cross-references (e.g. ``parent_event_id``) must never abort
    persistence of an otherwise valid record because of a malformed id.
    """
    if not value:
        return None
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


class Phase6A2PersistService:
    """Persists Phase 6A.2 temporal localisation results and evidence graphs.

    Each analysis run has at most one localisation result and one evidence
    graph; re-running analysis replaces the prior row (and its children via
    ``ondelete=CASCADE``) rather than accumulating duplicates.
    """

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def persist_temporal(
        self,
        result: TemporalLocalisationResult,
    ) -> TemporalLocalisationResultRow:
        if not result.organization_id:
            raise ValueError("TemporalLocalisationResult.organization_id is required to persist")
        if not result.analysis_id:
            raise ValueError("TemporalLocalisationResult.analysis_id is required to persist")

        organization_id = UUID(result.organization_id)
        analysis_run_id = UUID(result.analysis_id)

        existing_id = await self._session.scalar(
            select(TemporalLocalisationResultRow.id).where(
                TemporalLocalisationResultRow.organization_id == organization_id,
                TemporalLocalisationResultRow.analysis_run_id == analysis_run_id,
            )
        )
        if existing_id is not None:
            await self._session.execute(
                delete(TemporalLocalisationResultRow).where(
                    TemporalLocalisationResultRow.id == existing_id
                )
            )
            await self._session.flush()

        row = TemporalLocalisationResultRow(
            organization_id=organization_id,
            project_id=_optional_uuid(result.project_id),
            incident_id=_optional_uuid(getattr(result, "incident_id", None)),
            analysis_run_id=analysis_run_id,
            artifact_bundle_id=_optional_uuid(result.artifact_bundle_id),
            status=_enum_value(result.status),
            primary_failure_event_id=result.primary_failure_event_id,
            primary_failure_type=result.primary_failure_type,
            primary_failure_summary=result.primary_failure_summary,
            ordering_method=_enum_value(result.ordering_method),
            timestamp_quality=_enum_value(result.timestamp_quality),
            confidence=result.confidence,
            heuristic_version=result.heuristic_version,
            warnings=list(result.warnings),
            missing_information=list(result.missing_information),
            downstream_symptom_event_ids=list(result.downstream_symptom_event_ids),
            upstream_context_event_ids=list(result.upstream_context_event_ids),
            duration_ms=result.duration_ms,
        )
        self._session.add(row)
        await self._session.flush()

        for event in result.events:
            source_location = event.source_location
            event_org_id = _optional_uuid(event.organization_id) or organization_id
            self._session.add(
                TemporalEventRow(
                    organization_id=event_org_id,
                    project_id=_optional_uuid(event.project_id) or row.project_id,
                    analysis_run_id=analysis_run_id,
                    localisation_id=row.id,
                    artifact_id=_optional_uuid(event.artifact_id),
                    event_key=str(event.id),
                    event_type=_enum_value(event.event_type),
                    sequence_index=event.sequence_index,
                    event_timestamp=event.timestamp,
                    workflow_name=event.workflow_name,
                    job_name=event.job_name,
                    step_name=event.step_name,
                    command=event.command,
                    exit_code=event.exit_code,
                    message=event.message,
                    severity=event.severity,
                    source_path=source_location.path if source_location else None,
                    line_start=source_location.line_start if source_location else None,
                    line_end=source_location.line_end if source_location else None,
                    parser_entity_id=event.parser_entity_id,
                    parent_event_id=_optional_uuid(event.parent_event_id),
                    is_failure=event.is_failure,
                    is_candidate_primary_failure=event.is_candidate_primary_failure,
                    extraction_confidence=event.extraction_confidence,
                    event_metadata=dict(event.metadata),
                )
            )

        for link in result.causal_precedence_links:
            self._session.add(
                TemporalEventLinkRow(
                    organization_id=organization_id,
                    analysis_run_id=analysis_run_id,
                    localisation_id=row.id,
                    source_event_key=str(link.source_event_id),
                    target_event_key=str(link.target_event_id),
                    link_type=_enum_value(link.link_type),
                    derivation=_enum_value(link.derivation),
                    confidence=link.confidence,
                    explanation=link.explanation,
                    supporting_event_ids=list(link.supporting_event_ids),
                    rule_id=link.rule_id,
                    rule_version=link.rule_version,
                    proven_causality=link.proven_causality,
                )
            )

        await self._session.flush()
        logger.info(
            "temporal_localisation_persisted",
            localisation_id=str(row.id),
            analysis_run_id=str(analysis_run_id),
            event_count=len(result.events),
            link_count=len(result.causal_precedence_links),
        )
        return row

    async def persist_graph(
        self,
        graph: EvidenceGraph,
        consistency: GraphConsistencyReport | None = None,
    ) -> EvidenceGraphRow:
        if not graph.organization_id:
            raise ValueError("EvidenceGraph.organization_id is required to persist")
        if not graph.analysis_id:
            raise ValueError("EvidenceGraph.analysis_id is required to persist")

        organization_id = UUID(graph.organization_id)
        analysis_run_id = UUID(graph.analysis_id)
        effective_consistency = consistency if consistency is not None else graph.consistency

        existing_id = await self._session.scalar(
            select(EvidenceGraphRow.id).where(
                EvidenceGraphRow.organization_id == organization_id,
                EvidenceGraphRow.analysis_run_id == analysis_run_id,
            )
        )
        if existing_id is not None:
            await self._session.execute(
                delete(EvidenceGraphRow).where(EvidenceGraphRow.id == existing_id)
            )
            await self._session.flush()

        row = EvidenceGraphRow(
            organization_id=organization_id,
            project_id=_optional_uuid(graph.project_id),
            incident_id=_optional_uuid(graph.incident_id),
            analysis_run_id=analysis_run_id,
            artifact_bundle_id=_optional_uuid(graph.artifact_bundle_id),
            status=_enum_value(graph.status),
            builder_version=graph.builder_version,
            warnings=list(graph.warnings),
            errors=list(graph.errors),
            missing_link_diagnostics=list(graph.missing_link_diagnostics),
            metrics=_dataclass_to_dict(graph.metrics),
        )
        self._session.add(row)
        await self._session.flush()

        node_id_to_row_id: dict[str, UUID] = {}
        for node in graph.nodes:
            node_row = EvidenceGraphNodeRow(
                organization_id=organization_id,
                project_id=_optional_uuid(node.project_id) or row.project_id,
                analysis_run_id=analysis_run_id,
                graph_id=row.id,
                artifact_id=_optional_uuid(node.artifact_id),
                stable_key=node.stable_key,
                node_type=_enum_value(node.node_type),
                label=node.label,
                parser_entity_id=node.parser_entity_id,
                source_path=node.source_path,
                line_start=node.line_start,
                line_end=node.line_end,
                extraction_method=node.extraction_method,
                confidence=node.confidence,
                node_metadata=dict(node.metadata),
            )
            self._session.add(node_row)
            await self._session.flush()
            node_id_to_row_id[node.id] = node_row.id

        for edge in graph.edges:
            source_row_id = node_id_to_row_id.get(edge.source_node_id)
            target_row_id = node_id_to_row_id.get(edge.target_node_id)
            if source_row_id is None or target_row_id is None:
                logger.warning(
                    "evidence_graph_edge_skipped_unresolved_node",
                    graph_id=str(row.id),
                    edge_stable_key=edge.stable_key,
                )
                continue
            self._session.add(
                EvidenceGraphEdgeRow(
                    organization_id=organization_id,
                    analysis_run_id=analysis_run_id,
                    graph_id=row.id,
                    source_node_id=source_row_id,
                    target_node_id=target_row_id,
                    stable_key=edge.stable_key,
                    edge_type=_enum_value(edge.edge_type),
                    derivation_type=_enum_value(edge.derivation_type),
                    confidence=edge.confidence,
                    explanation=edge.explanation,
                    rule_id=edge.rule_id,
                    rule_version=edge.rule_version,
                    evidence_ids=list(edge.evidence_ids),
                )
            )

        if effective_consistency is not None:
            self._session.add(
                GraphConsistencyReportRow(
                    organization_id=organization_id,
                    analysis_run_id=analysis_run_id,
                    graph_id=row.id,
                    status=_enum_value(effective_consistency.status),
                    valid_node_count=effective_consistency.valid_node_count,
                    valid_edge_count=effective_consistency.valid_edge_count,
                    consistency_score=effective_consistency.consistency_score,
                    invalid_edge_ids=list(effective_consistency.invalid_edge_ids),
                    warnings=list(effective_consistency.warnings),
                    errors=list(effective_consistency.errors),
                    orphan_nodes=list(effective_consistency.orphan_nodes),
                    missing_expected_links=list(effective_consistency.missing_expected_links),
                    conflicting_links=list(effective_consistency.conflicting_links),
                    rule_results=[
                        _dataclass_to_dict(r) for r in effective_consistency.rule_results
                    ],
                )
            )

        await self._session.flush()
        logger.info(
            "evidence_graph_persisted",
            graph_id=str(row.id),
            analysis_run_id=str(analysis_run_id),
            node_count=len(graph.nodes),
            edge_count=len(graph.edges),
        )
        return row
