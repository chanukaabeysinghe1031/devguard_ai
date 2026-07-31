"""Debug/read APIs for Phase 6A.2 temporal localisation and evidence graphs."""

from __future__ import annotations

from math import ceil
from uuid import UUID

from sqlalchemy import func, select

from app.application.services.analysis_run_service import AnalysisRunService
from app.domain.exceptions.business import ResourceNotFoundError
from app.infrastructure.database.models.temporal_evidence_graph import (
    EvidenceGraphEdgeRow,
    EvidenceGraphNodeRow,
    EvidenceGraphRow,
    GraphConsistencyReportRow,
    TemporalEventRow,
    TemporalLocalisationResultRow,
)
from app.schemas.phase6a2 import (
    EvidenceGraphEdgeItem,
    EvidenceGraphEdgeListResponse,
    EvidenceGraphNodeItem,
    EvidenceGraphNodeListResponse,
    EvidenceGraphSummaryResponse,
    GraphConsistencyResponse,
    TemporalEventItem,
    TemporalEventListResponse,
    TemporalLocalisationResponse,
)


class Phase6A2ArtifactsService:
    """Org-scoped read APIs for temporal + evidence graph debug views."""

    def __init__(self, run_service: AnalysisRunService) -> None:
        self._runs = run_service
        self._session = run_service._session  # noqa: SLF001

    async def get_temporal_localisation(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
    ) -> TemporalLocalisationResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        row = await self._session.scalar(
            select(TemporalLocalisationResultRow).where(
                TemporalLocalisationResultRow.organization_id == organization_id,
                TemporalLocalisationResultRow.analysis_run_id == analysis_run_id,
            )
        )
        if row is None:
            raise ResourceNotFoundError("Temporal localisation not found for this analysis.")
        return TemporalLocalisationResponse(
            id=row.id,
            analysis_run_id=row.analysis_run_id,
            status=row.status,
            primary_failure_event_id=row.primary_failure_event_id,
            primary_failure_type=row.primary_failure_type,
            primary_failure_summary=row.primary_failure_summary,
            ordering_method=row.ordering_method,
            timestamp_quality=row.timestamp_quality,
            confidence=row.confidence,
            heuristic_version=row.heuristic_version,
            warnings=list(row.warnings or []),
            missing_information=list(row.missing_information or []),
            downstream_symptom_event_ids=list(row.downstream_symptom_event_ids or []),
            upstream_context_event_ids=list(row.upstream_context_event_ids or []),
            duration_ms=row.duration_ms,
            created_at=row.created_at,
        )

    async def list_temporal_events(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        page: int = 1,
        page_size: int = 100,
        event_type: str | None = None,
    ) -> TemporalEventListResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        page = max(1, page)
        page_size = min(max(1, page_size), 200)
        filters = [
            TemporalEventRow.organization_id == organization_id,
            TemporalEventRow.analysis_run_id == analysis_run_id,
        ]
        if event_type:
            filters.append(TemporalEventRow.event_type == event_type)
        total = int(
            await self._session.scalar(
                select(func.count()).select_from(TemporalEventRow).where(*filters)
            )
            or 0
        )
        rows = list(
            (
                await self._session.scalars(
                    select(TemporalEventRow)
                    .where(*filters)
                    .order_by(TemporalEventRow.sequence_index.asc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return TemporalEventListResponse(
            items=[
                TemporalEventItem(
                    id=r.id,
                    event_key=r.event_key,
                    event_type=r.event_type,
                    sequence_index=r.sequence_index,
                    event_timestamp=r.event_timestamp,
                    job_name=r.job_name,
                    step_name=r.step_name,
                    message=r.message,
                    severity=r.severity,
                    is_failure=r.is_failure,
                    is_candidate_primary_failure=r.is_candidate_primary_failure,
                    source_path=r.source_path,
                    line_start=r.line_start,
                    line_end=r.line_end,
                    extraction_confidence=r.extraction_confidence,
                )
                for r in rows
            ],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=max(1, ceil(total / page_size)) if total else 1,
        )

    async def get_evidence_graph(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
    ) -> EvidenceGraphSummaryResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        row = await self._session.scalar(
            select(EvidenceGraphRow).where(
                EvidenceGraphRow.organization_id == organization_id,
                EvidenceGraphRow.analysis_run_id == analysis_run_id,
            )
        )
        if row is None:
            raise ResourceNotFoundError("Evidence graph not found for this analysis.")
        metrics = row.metrics if isinstance(row.metrics, dict) else {}
        return EvidenceGraphSummaryResponse(
            id=row.id,
            analysis_run_id=row.analysis_run_id,
            status=row.status,
            builder_version=row.builder_version,
            node_count=int(metrics.get("node_count") or 0),
            edge_count=int(metrics.get("edge_count") or 0),
            metrics=metrics,
            warnings=list(row.warnings or []),
            errors=list(row.errors or []),
            missing_link_diagnostics=list(row.missing_link_diagnostics or []),
            created_at=row.created_at,
        )

    async def list_graph_nodes(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        page: int = 1,
        page_size: int = 100,
        node_type: str | None = None,
        artifact_id: UUID | None = None,
        source_path: str | None = None,
    ) -> EvidenceGraphNodeListResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        page = max(1, page)
        page_size = min(max(1, page_size), 200)
        filters = [
            EvidenceGraphNodeRow.organization_id == organization_id,
            EvidenceGraphNodeRow.analysis_run_id == analysis_run_id,
        ]
        if node_type:
            filters.append(EvidenceGraphNodeRow.node_type == node_type)
        if artifact_id:
            filters.append(EvidenceGraphNodeRow.artifact_id == artifact_id)
        if source_path:
            filters.append(EvidenceGraphNodeRow.source_path == source_path)
        total = int(
            await self._session.scalar(
                select(func.count()).select_from(EvidenceGraphNodeRow).where(*filters)
            )
            or 0
        )
        rows = list(
            (
                await self._session.scalars(
                    select(EvidenceGraphNodeRow)
                    .where(*filters)
                    .order_by(
                        EvidenceGraphNodeRow.node_type.asc(),
                        EvidenceGraphNodeRow.label.asc(),
                    )
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return EvidenceGraphNodeListResponse(
            items=[
                EvidenceGraphNodeItem(
                    id=r.id,
                    stable_key=r.stable_key,
                    node_type=r.node_type,
                    label=r.label,
                    artifact_id=r.artifact_id,
                    source_path=r.source_path,
                    line_start=r.line_start,
                    line_end=r.line_end,
                    confidence=r.confidence,
                    extraction_method=r.extraction_method,
                )
                for r in rows
            ],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=max(1, ceil(total / page_size)) if total else 1,
        )

    async def list_graph_edges(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        page: int = 1,
        page_size: int = 100,
        edge_type: str | None = None,
        derivation_type: str | None = None,
    ) -> EvidenceGraphEdgeListResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        page = max(1, page)
        page_size = min(max(1, page_size), 200)
        filters = [
            EvidenceGraphEdgeRow.organization_id == organization_id,
            EvidenceGraphEdgeRow.analysis_run_id == analysis_run_id,
        ]
        if edge_type:
            filters.append(EvidenceGraphEdgeRow.edge_type == edge_type)
        if derivation_type:
            filters.append(EvidenceGraphEdgeRow.derivation_type == derivation_type)
        total = int(
            await self._session.scalar(
                select(func.count()).select_from(EvidenceGraphEdgeRow).where(*filters)
            )
            or 0
        )
        rows = list(
            (
                await self._session.scalars(
                    select(EvidenceGraphEdgeRow)
                    .where(*filters)
                    .order_by(EvidenceGraphEdgeRow.edge_type.asc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return EvidenceGraphEdgeListResponse(
            items=[
                EvidenceGraphEdgeItem(
                    id=r.id,
                    source_node_id=r.source_node_id,
                    target_node_id=r.target_node_id,
                    edge_type=r.edge_type,
                    derivation_type=r.derivation_type,
                    confidence=r.confidence,
                    explanation=r.explanation,
                    rule_id=r.rule_id,
                    rule_version=r.rule_version,
                )
                for r in rows
            ],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=max(1, ceil(total / page_size)) if total else 1,
        )

    async def get_graph_consistency(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
    ) -> GraphConsistencyResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        row = await self._session.scalar(
            select(GraphConsistencyReportRow)
            .where(
                GraphConsistencyReportRow.organization_id == organization_id,
                GraphConsistencyReportRow.analysis_run_id == analysis_run_id,
            )
            .order_by(GraphConsistencyReportRow.created_at.desc())
            .limit(1)
        )
        if row is None:
            raise ResourceNotFoundError("Graph consistency report not found.")
        return GraphConsistencyResponse(
            id=row.id,
            graph_id=row.graph_id,
            analysis_run_id=row.analysis_run_id,
            status=row.status,
            valid_node_count=row.valid_node_count,
            valid_edge_count=row.valid_edge_count,
            consistency_score=row.consistency_score,
            invalid_edge_ids=list(row.invalid_edge_ids or []),
            warnings=list(row.warnings or []),
            errors=list(row.errors or []),
            orphan_nodes=list(row.orphan_nodes or []),
            missing_expected_links=list(row.missing_expected_links or []),
            conflicting_links=list(row.conflicting_links or []),
            rule_results=list(row.rule_results or []),
            created_at=row.created_at,
        )
