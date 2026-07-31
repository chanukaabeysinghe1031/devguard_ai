"""Debug/read APIs for Phase 6A.5 hypothesis-directed retrieval."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select

from app.application.services.analysis_run_service import AnalysisRunService
from app.domain.exceptions.business import ResourceNotFoundError
from app.infrastructure.database.models.hypothesis_retrieval import (
    HypothesisRetrievalQueryExecutionRow,
    HypothesisRetrievalRunRow,
    HypothesisRetrievalSessionRow,
    HypothesisRetrievedItemQueryRow,
    HypothesisRetrievedItemRow,
)
from app.schemas.phase6a5 import (
    HypothesisRetrievalContextResponse,
    HypothesisRetrievalPlanResponse,
    HypothesisRetrievalQueryItem,
    HypothesisRetrievalQueryListResponse,
    HypothesisRetrievalRunResponse,
    HypothesisRetrievalSessionDetailResponse,
    HypothesisRetrievalSessionListItem,
    HypothesisRetrievalSessionListResponse,
    HypothesisRetrievedItemListResponse,
    HypothesisRetrievedItemResponse,
)


class Phase6A5HypothesisRetrievalService:
    def __init__(self, run_service: AnalysisRunService) -> None:
        self._runs = run_service
        self._session = run_service._session  # noqa: SLF001

    async def get_run(
        self, *, organization_id: UUID, analysis_run_id: UUID
    ) -> HypothesisRetrievalRunResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        row = await self._session.scalar(
            select(HypothesisRetrievalRunRow).where(
                HypothesisRetrievalRunRow.organization_id == organization_id,
                HypothesisRetrievalRunRow.analysis_run_id == analysis_run_id,
            )
        )
        if row is None:
            raise ResourceNotFoundError("Hypothesis retrieval run not found.")
        return HypothesisRetrievalRunResponse(
            id=row.id,
            analysis_run_id=row.analysis_run_id,
            hypothesis_generation_run_id=row.hypothesis_generation_run_id,
            status=row.status,
            execution_mode=row.execution_mode,
            hypothesis_count_requested=row.hypothesis_count_requested,
            hypothesis_count_processed=row.hypothesis_count_processed,
            session_count_complete=row.session_count_complete,
            session_count_partial=row.session_count_partial,
            session_count_failed=row.session_count_failed,
            total_query_count=row.total_query_count,
            total_result_count=row.total_result_count,
            total_unique_source_count=row.total_unique_source_count,
            duration_ms=row.duration_ms,
            embedding_model_version=row.embedding_model_version,
            retrieval_pipeline_version=row.retrieval_pipeline_version,
            error_summary=row.error_summary,
            warnings=[str(x) for x in (row.warnings or [])],
            configuration_snapshot=dict(row.configuration_snapshot or {}),
            created_at=row.created_at,
        )

    async def list_sessions(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        status: str | None = None,
    ) -> HypothesisRetrievalSessionListResponse:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        filters = [
            HypothesisRetrievalSessionRow.organization_id == organization_id,
            HypothesisRetrievalSessionRow.analysis_run_id == analysis_run_id,
        ]
        if status:
            filters.append(HypothesisRetrievalSessionRow.status == status)
        rows = list(
            (
                await self._session.scalars(
                    select(HypothesisRetrievalSessionRow)
                    .where(*filters)
                    .order_by(HypothesisRetrievalSessionRow.created_at.asc())
                )
            ).all()
        )
        items = [
            HypothesisRetrievalSessionListItem(
                id=r.id,
                hypothesis_id=r.hypothesis_id,
                hypothesis_key=r.hypothesis_key,
                status=r.status,
                execution_mode=r.execution_mode,
                category_code=r.category_code,
                query_count=r.query_count,
                accepted_result_count=r.accepted_result_count,
                unique_source_count=r.unique_source_count,
                duration_ms=r.duration_ms,
                warnings=[str(x) for x in (r.warnings or [])],
            )
            for r in rows
        ]
        return HypothesisRetrievalSessionListResponse(items=items, total_items=len(items))

    async def get_session(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        session_id: UUID,
    ) -> HypothesisRetrievalSessionDetailResponse:
        row = await self._load_session(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            session_id=session_id,
        )
        return HypothesisRetrievalSessionDetailResponse(
            id=row.id,
            retrieval_run_id=row.retrieval_run_id,
            analysis_run_id=row.analysis_run_id,
            hypothesis_id=row.hypothesis_id,
            hypothesis_key=row.hypothesis_key,
            status=row.status,
            execution_mode=row.execution_mode,
            retrieval_context_version=row.retrieval_context_version,
            retrieval_plan_version=row.retrieval_plan_version,
            hypothesis_prior_score_snapshot=row.hypothesis_prior_score_snapshot,
            category_code=row.category_code,
            causal_claim_snapshot=row.causal_claim_snapshot,
            affected_artifact_id=row.affected_artifact_id,
            root_cause_node_id=row.root_cause_node_id,
            observed_failure_node_id=row.observed_failure_node_id,
            query_count=row.query_count,
            raw_result_count=row.raw_result_count,
            accepted_result_count=row.accepted_result_count,
            unique_source_count=row.unique_source_count,
            cache_hit_count=row.cache_hit_count,
            source_types_attempted=[str(x) for x in (row.source_types_attempted or [])],
            source_types_succeeded=[str(x) for x in (row.source_types_succeeded or [])],
            source_types_unavailable=[str(x) for x in (row.source_types_unavailable or [])],
            metrics=dict(row.metrics or {}),
            duration_ms=row.duration_ms,
            warnings=[str(x) for x in (row.warnings or [])],
            errors=[str(x) for x in (row.errors or [])],
            created_at=row.created_at,
        )

    async def get_context(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        session_id: UUID,
    ) -> HypothesisRetrievalContextResponse:
        row = await self._load_session(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            session_id=session_id,
        )
        snapshot = dict(row.context_snapshot or {})
        # Never expose excluded sensitive fields contents beyond redacted snapshot.
        snapshot.pop("raw_secrets", None)
        return HypothesisRetrievalContextResponse(
            session_id=row.id,
            context_version=row.retrieval_context_version,
            snapshot=snapshot,
        )

    async def get_plan(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        session_id: UUID,
    ) -> HypothesisRetrievalPlanResponse:
        row = await self._load_session(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            session_id=session_id,
        )
        return HypothesisRetrievalPlanResponse(
            session_id=row.id,
            plan_version=row.retrieval_plan_version,
            snapshot=dict(row.plan_snapshot or {}),
        )

    async def list_queries(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        session_id: UUID,
        query_type: str | None = None,
    ) -> HypothesisRetrievalQueryListResponse:
        await self._load_session(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            session_id=session_id,
        )
        filters = [
            HypothesisRetrievalQueryExecutionRow.organization_id == organization_id,
            HypothesisRetrievalQueryExecutionRow.session_id == session_id,
        ]
        if query_type:
            filters.append(HypothesisRetrievalQueryExecutionRow.query_type == query_type)
        rows = list(
            (
                await self._session.scalars(
                    select(HypothesisRetrievalQueryExecutionRow)
                    .where(*filters)
                    .order_by(HypothesisRetrievalQueryExecutionRow.created_at.asc())
                )
            ).all()
        )
        items = [
            HypothesisRetrievalQueryItem(
                id=r.id,
                query_id=r.query_id,
                query_type=r.query_type,
                normalized_query=r.normalized_query,
                source_types=[str(x) for x in (r.source_types or [])],
                status=r.status,
                adapters_attempted=[str(x) for x in (r.adapters_attempted or [])],
                adapters_succeeded=[str(x) for x in (r.adapters_succeeded or [])],
                raw_result_count=r.raw_result_count,
                accepted_result_count=r.accepted_result_count,
                cache_hit=bool(r.cache_hit),
                duration_ms=r.duration_ms,
                failure_type=r.failure_type,
                warnings=[str(x) for x in (r.warnings or [])],
                error_summary=r.error_summary,
            )
            for r in rows
        ]
        return HypothesisRetrievalQueryListResponse(items=items, total_items=len(items))

    async def list_items(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        session_id: UUID,
        page: int = 1,
        page_size: int = 50,
        source_type: str | None = None,
        adapter_name: str | None = None,
        artifact_id: str | None = None,
        graph_node_id: str | None = None,
        historical_incident_id: str | None = None,
        min_retrieval_score: float | None = None,
    ) -> HypothesisRetrievedItemListResponse:
        await self._load_session(
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            session_id=session_id,
        )
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        filters = [
            HypothesisRetrievedItemRow.organization_id == organization_id,
            HypothesisRetrievedItemRow.session_id == session_id,
        ]
        if source_type:
            filters.append(HypothesisRetrievedItemRow.source_type == source_type)
        if adapter_name:
            filters.append(HypothesisRetrievedItemRow.adapter_name == adapter_name)
        if artifact_id:
            filters.append(HypothesisRetrievedItemRow.artifact_id == artifact_id)
        if graph_node_id:
            filters.append(HypothesisRetrievedItemRow.graph_node_id == graph_node_id)
        if historical_incident_id:
            filters.append(
                HypothesisRetrievedItemRow.historical_incident_id == historical_incident_id
            )
        if min_retrieval_score is not None:
            filters.append(HypothesisRetrievedItemRow.retrieval_score >= float(min_retrieval_score))

        total = int(
            await self._session.scalar(
                select(func.count())
                .select_from(HypothesisRetrievedItemRow)
                .where(*filters)
            )
            or 0
        )
        rows = list(
            (
                await self._session.scalars(
                    select(HypothesisRetrievedItemRow)
                    .where(*filters)
                    .order_by(HypothesisRetrievedItemRow.global_session_order.asc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        items: list[HypothesisRetrievedItemResponse] = []
        for r in rows:
            assoc = list(
                (
                    await self._session.scalars(
                        select(HypothesisRetrievedItemQueryRow.query_id).where(
                            HypothesisRetrievedItemQueryRow.item_id == r.id
                        )
                    )
                ).all()
            )
            items.append(
                HypothesisRetrievedItemResponse(
                    id=r.id,
                    primary_query_id=r.primary_query_id,
                    source_type=r.source_type,
                    source_system=r.source_system,
                    source_id=r.source_id,
                    document_id=r.document_id,
                    chunk_id=r.chunk_id,
                    artifact_id=r.artifact_id,
                    graph_node_id=r.graph_node_id,
                    graph_edge_id=r.graph_edge_id,
                    temporal_event_id=r.temporal_event_id,
                    historical_incident_id=r.historical_incident_id,
                    title=r.title,
                    text_excerpt=r.text_excerpt,
                    source_path=r.source_path,
                    line_start=r.line_start,
                    line_end=r.line_end,
                    retrieval_score=r.retrieval_score,
                    lexical_score=r.lexical_score,
                    vector_score=r.vector_score,
                    historical_score=r.historical_score,
                    adapter_name=r.adapter_name,
                    adapter_version=r.adapter_version,
                    relation_candidate=r.relation_candidate,
                    rank_within_query=r.rank_within_query,
                    global_session_order=r.global_session_order,
                    redaction_status=r.redaction_status,
                    associated_query_ids=[str(x) for x in assoc],
                )
            )
        return HypothesisRetrievedItemListResponse(
            items=items,
            total_items=total,
            page=page,
            page_size=page_size,
        )

    async def _load_session(
        self,
        *,
        organization_id: UUID,
        analysis_run_id: UUID,
        session_id: UUID,
    ) -> HypothesisRetrievalSessionRow:
        await self._runs._load_run(organization_id, analysis_run_id)  # noqa: SLF001
        row = await self._session.scalar(
            select(HypothesisRetrievalSessionRow).where(
                HypothesisRetrievalSessionRow.organization_id == organization_id,
                HypothesisRetrievalSessionRow.analysis_run_id == analysis_run_id,
                HypothesisRetrievalSessionRow.id == session_id,
            )
        )
        if row is None:
            raise ResourceNotFoundError("Hypothesis retrieval session not found.")
        return row
