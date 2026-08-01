"""Persist Phase 6A.5 hypothesis-directed retrieval runs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.hypothesis_retrieval.models import (
    HypothesisRetrievalRun,
    HypothesisRetrievalSession,
    HypothesisRetrievedItem,
)
from app.infrastructure.database.models.hypothesis_retrieval import (
    HypothesisRetrievalQueryExecutionRow,
    HypothesisRetrievalRunRow,
    HypothesisRetrievalSessionRow,
    HypothesisRetrievedItemQueryRow,
    HypothesisRetrievedItemRow,
)


class HypothesisRetrievalPersistService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def persist(self, run: HypothesisRetrievalRun) -> HypothesisRetrievalRunRow:
        org_id = UUID(run.organization_id)
        analysis_id = UUID(run.analysis_id)

        existing = await self._session.scalar(
            select(HypothesisRetrievalRunRow).where(
                HypothesisRetrievalRunRow.organization_id == org_id,
                HypothesisRetrievalRunRow.analysis_run_id == analysis_id,
            )
        )
        if existing is not None:
            session_ids = list(
                (
                    await self._session.scalars(
                        select(HypothesisRetrievalSessionRow.id).where(
                            HypothesisRetrievalSessionRow.retrieval_run_id == existing.id
                        )
                    )
                ).all()
            )
            if session_ids:
                item_ids = list(
                    (
                        await self._session.scalars(
                            select(HypothesisRetrievedItemRow.id).where(
                                HypothesisRetrievedItemRow.session_id.in_(session_ids)
                            )
                        )
                    ).all()
                )
                if item_ids:
                    await self._session.execute(
                        delete(HypothesisRetrievedItemQueryRow).where(
                            HypothesisRetrievedItemQueryRow.item_id.in_(item_ids)
                        )
                    )
                    await self._session.execute(
                        delete(HypothesisRetrievedItemRow).where(
                            HypothesisRetrievedItemRow.id.in_(item_ids)
                        )
                    )
                await self._session.execute(
                    delete(HypothesisRetrievalQueryExecutionRow).where(
                        HypothesisRetrievalQueryExecutionRow.session_id.in_(session_ids)
                    )
                )
                await self._session.execute(
                    delete(HypothesisRetrievalSessionRow).where(
                        HypothesisRetrievalSessionRow.id.in_(session_ids)
                    )
                )
            await self._session.delete(existing)
            await self._session.flush()

        row = HypothesisRetrievalRunRow(
            organization_id=org_id,
            project_id=UUID(run.project_id) if run.project_id else None,
            incident_id=UUID(run.incident_id) if run.incident_id else None,
            analysis_run_id=analysis_id,
            hypothesis_generation_run_id=(
                UUID(run.hypothesis_generation_run_id) if run.hypothesis_generation_run_id else None
            ),
            status=run.status.value,
            execution_mode=run.execution_mode.value,
            hypothesis_count_requested=run.hypothesis_count_requested,
            hypothesis_count_processed=run.hypothesis_count_processed,
            session_count_complete=run.session_count_complete,
            session_count_partial=run.session_count_partial,
            session_count_failed=run.session_count_failed,
            total_query_count=run.total_query_count,
            total_result_count=run.total_result_count,
            total_unique_source_count=run.total_unique_source_count,
            started_at=run.started_at,
            completed_at=run.completed_at,
            duration_ms=run.duration_ms,
            configuration_snapshot=dict(run.configuration_snapshot),
            embedding_model_version=run.embedding_model_version,
            retrieval_pipeline_version=run.retrieval_pipeline_version,
            error_summary=run.error_summary,
            warnings=list(run.warnings),
        )
        self._session.add(row)
        await self._session.flush()
        run.id = str(row.id)

        for sess in run.sessions:
            srow = HypothesisRetrievalSessionRow(
                retrieval_run_id=row.id,
                organization_id=org_id,
                project_id=UUID(sess.project_id) if sess.project_id else None,
                incident_id=UUID(sess.incident_id) if sess.incident_id else None,
                analysis_run_id=analysis_id,
                hypothesis_id=UUID(sess.hypothesis_id),
                hypothesis_key=sess.hypothesis_key,
                status=sess.status.value,
                execution_mode=sess.execution_mode.value,
                retrieval_context_version=sess.retrieval_context_version,
                retrieval_plan_version=sess.retrieval_plan_version,
                hypothesis_prior_score_snapshot=sess.hypothesis_prior_score_snapshot,
                category_code=sess.category_code,
                causal_claim_snapshot=sess.causal_claim_snapshot,
                affected_artifact_id=sess.affected_artifact_id,
                root_cause_node_id=sess.root_cause_node_id,
                observed_failure_node_id=sess.observed_failure_node_id,
                query_count=sess.query_count,
                raw_result_count=sess.raw_result_count,
                accepted_result_count=sess.accepted_result_count,
                unique_source_count=sess.unique_source_count,
                cache_hit_count=sess.cache_hit_count,
                source_types_attempted=list(sess.source_types_attempted),
                source_types_succeeded=list(sess.source_types_succeeded),
                source_types_unavailable=list(sess.source_types_unavailable),
                context_snapshot=sess.context.to_dict() if sess.context else {},
                plan_snapshot=_plan_snapshot(sess),
                metrics=dict(sess.metrics),
                started_at=sess.started_at,
                completed_at=sess.completed_at,
                duration_ms=sess.duration_ms,
                warnings=list(sess.warnings),
                errors=list(sess.errors),
            )
            self._session.add(srow)
            await self._session.flush()
            sess.id = str(srow.id)
            sess.retrieval_run_id = str(row.id)

            query_row_by_qid: dict[str, UUID] = {}
            for qex in sess.query_executions:
                qrow = HypothesisRetrievalQueryExecutionRow(
                    session_id=srow.id,
                    organization_id=org_id,
                    analysis_run_id=analysis_id,
                    query_id=qex.query_id,
                    query_type=qex.query_type.value,
                    normalized_query=qex.normalized_query,
                    source_types=[s.value for s in qex.source_types],
                    status=qex.status,
                    adapters_attempted=list(qex.adapters_attempted),
                    adapters_succeeded=list(qex.adapters_succeeded),
                    raw_result_count=qex.raw_result_count,
                    accepted_result_count=qex.accepted_result_count,
                    cache_hit=qex.cache_hit,
                    started_at=qex.started_at,
                    completed_at=qex.completed_at,
                    duration_ms=qex.duration_ms,
                    failure_type=qex.failure_type.value if qex.failure_type else None,
                    warnings=list(qex.warnings),
                    error_summary=qex.error_summary,
                )
                self._session.add(qrow)
                await self._session.flush()
                qex.id = str(qrow.id)
                qex.session_id = str(srow.id)
                query_row_by_qid[qex.query_id] = qrow.id

            item_rows: list[tuple[HypothesisRetrievedItem, HypothesisRetrievedItemRow]] = []
            for item in sess.items:
                irow = HypothesisRetrievedItemRow(
                    session_id=srow.id,
                    organization_id=org_id,
                    analysis_run_id=analysis_id,
                    hypothesis_id=UUID(sess.hypothesis_id),
                    primary_query_id=item.query_id,
                    source_type=item.source_type.value,
                    source_system=item.source_system,
                    source_id=item.source_id,
                    document_id=item.document_id,
                    chunk_id=item.chunk_id,
                    artifact_id=item.artifact_id,
                    graph_node_id=item.graph_node_id,
                    graph_edge_id=item.graph_edge_id,
                    temporal_event_id=item.temporal_event_id,
                    historical_incident_id=item.historical_incident_id,
                    title=(item.title or "")[:500] or None,
                    text_excerpt=item.text_excerpt,
                    normalized_text_hash=item.normalized_text_hash,
                    source_path=item.source_path,
                    line_start=item.line_start,
                    line_end=item.line_end,
                    repository=item.repository,
                    commit_sha=item.commit_sha,
                    source_timestamp=item.source_timestamp,
                    retrieval_score=item.retrieval_score,
                    lexical_score=item.lexical_score,
                    vector_score=item.vector_score,
                    historical_score=item.historical_score,
                    graph_distance=item.graph_distance,
                    adapter_name=item.adapter_name,
                    adapter_version=item.adapter_version,
                    embedding_model_version=item.embedding_model_version,
                    relation_candidate=item.relation_candidate.value,
                    rank_within_query=item.rank_within_query,
                    global_session_order=item.global_session_order,
                    item_metadata={
                        **dict(item.metadata),
                        "associated_query_ids": list(item.associated_query_ids),
                        "contributing_adapters": list(item.contributing_adapters),
                    },
                    redaction_status=item.redaction_status,
                )
                self._session.add(irow)
                item_rows.append((item, irow))

            await self._session.flush()

            for item, irow in item_rows:
                item.id = str(irow.id)
                item.session_id = str(srow.id)
                query_ids = list(item.associated_query_ids) or [item.query_id]
                for qid in sorted(set(query_ids)):
                    self._session.add(
                        HypothesisRetrievedItemQueryRow(
                            item_id=irow.id,
                            query_execution_id=query_row_by_qid.get(qid),
                            query_id=qid,
                            adapter_name=item.adapter_name,
                            retrieval_score=item.retrieval_score,
                        )
                    )

        await self._session.flush()
        return row


def _plan_snapshot(sess: HypothesisRetrievalSession) -> dict:
    snapshot = sess.plan.to_dict() if sess.plan is not None else {}
    adaptive = (sess.metrics or {}).get("adaptive_plan")
    if isinstance(adaptive, dict):
        snapshot = dict(snapshot)
        snapshot["adaptive_plan"] = adaptive
        basic = adaptive.get("basic_plan_snapshot")
        if isinstance(basic, dict):
            snapshot["basic_plan_snapshot"] = basic
    return snapshot
