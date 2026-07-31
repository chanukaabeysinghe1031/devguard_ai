"""Hypothesis-directed retrieval orchestrator (Phase 6A.5 Part 1B)."""

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.hypothesis_retrieval.adapters.artifact import ArtifactEvidenceRetrievalAdapter
from app.ai.hypothesis_retrieval.adapters.graph import GraphEvidenceRetrievalAdapter
from app.ai.hypothesis_retrieval.adapters.hybrid import HybridPipelineHypothesisAdapter
from app.ai.hypothesis_retrieval.adapters.temporal import TemporalEvidenceRetrievalAdapter
from app.ai.hypothesis_retrieval.cache import InMemoryRetrievalCache
from app.ai.hypothesis_retrieval.context_builder import HypothesisRetrievalContextBuilder
from app.ai.hypothesis_retrieval.dedupe import deduplicate_session_items
from app.ai.hypothesis_retrieval.persist import HypothesisRetrievalPersistService
from app.ai.hypothesis_retrieval.plan_builder import HypothesisRetrievalPlanBuilder
from app.ai.orchestration.analysis_context import AnalysisContext
from app.ai.rag.hybrid_pipeline import HybridRetrievalPipeline
from app.core.config import Settings
from app.domain.hypotheses.enums import CriticDecision, HypothesisStatus
from app.domain.hypothesis_retrieval.enums import (
    HypothesisRetrievalRunStatus,
    HypothesisRetrievalSessionStatus,
    HypothesisRetrievalSourceType,
    RetrievalExecutionMode,
    RetrievalFailureType,
)
from app.domain.hypothesis_retrieval.models import (
    RETRIEVAL_PIPELINE_VERSION,
    HypothesisRetrievalContext,
    HypothesisRetrievalQueryExecution,
    HypothesisRetrievalRun,
    HypothesisRetrievalSession,
    HypothesisRetrievedItem,
)
from app.infrastructure.database.models.causal_hypotheses import (
    CausalHypothesisRow,
    CausalHypothesisRunRow,
    HypothesisCriticResultRow,
)


def is_hypothesis_eligible_for_retrieval(
    *,
    status: str | None,
    critic_decision: str | None,
    missing_evidence: list[Any] | None = None,
) -> bool:
    """Eligibility helper for Phase 6A.5 retrieval sessions."""
    excluded = {
        HypothesisStatus.INVALID.value,
        HypothesisStatus.DUPLICATE.value,
        HypothesisStatus.REJECTED.value,
        HypothesisStatus.FAILED.value,
        HypothesisStatus.DISABLED.value,
        HypothesisStatus.CONTRADICTED.value,
    }
    if status in excluded:
        return False
    if critic_decision in {
        CriticDecision.CONTRADICTED.value,
        CriticDecision.REJECT.value,
    }:
        return False

    if status == HypothesisStatus.READY_FOR_RANKING.value:
        return True
    if critic_decision in {
        CriticDecision.ACCEPT_FOR_RANKING.value,
        CriticDecision.ACCEPT_WITH_WARNINGS.value,
    }:
        return True
    if status == HypothesisStatus.INCOMPLETE.value and bool(missing_evidence):
        return True
    return critic_decision == CriticDecision.INCOMPLETE.value and bool(missing_evidence)


class HypothesisDirectedRetrievalOrchestrator:
    """Per-hypothesis retrieval sessions after Phase 6A.4. Does not rank."""

    def __init__(
        self,
        settings: Settings,
        *,
        hybrid_pipeline: HybridRetrievalPipeline | None = None,
        cache: InMemoryRetrievalCache | None = None,
    ) -> None:
        self._settings = settings
        self._pipeline = hybrid_pipeline
        self._cache = cache
        if self._cache is None and settings.retrieval_cache_enabled:
            self._cache = InMemoryRetrievalCache()
        if not settings.retrieval_cache_enabled:
            self._cache = None

        self._artifact = ArtifactEvidenceRetrievalAdapter(
            enabled=settings.hypothesis_artifact_retrieval_enabled,
            max_items=settings.max_artifact_evidence_items_for_retrieval,
        )
        self._graph = GraphEvidenceRetrievalAdapter(
            enabled=settings.hypothesis_graph_context_enabled,
            max_items=settings.max_graph_context_nodes_for_retrieval,
        )
        self._temporal = TemporalEvidenceRetrievalAdapter(enabled=True)
        self._hybrid = HybridPipelineHypothesisAdapter(
            hybrid_pipeline,
            cache=self._cache,
            cache_enabled=settings.retrieval_cache_enabled,
            embedding_model_version=settings.embedding_model,
            historical_enabled=settings.hypothesis_historical_retrieval_enabled,
            static_kb_enabled=settings.hypothesis_static_kb_retrieval_enabled,
        )
        self._plan_builder = HypothesisRetrievalPlanBuilder(
            max_queries=settings.max_queries_per_hypothesis,
            max_query_chars=settings.max_retrieval_query_chars,
            max_results_per_query=settings.max_results_per_query,
            historical_enabled=settings.hypothesis_historical_retrieval_enabled,
            static_kb_enabled=settings.hypothesis_static_kb_retrieval_enabled,
            artifact_enabled=settings.hypothesis_artifact_retrieval_enabled,
            graph_context_enabled=settings.hypothesis_graph_context_enabled,
            multi_query_enabled=settings.multi_query_retrieval_enabled,
            timeout_seconds=settings.hypothesis_retrieval_timeout_seconds,
        )

    async def run(
        self,
        db: AsyncSession,
        analysis_context: AnalysisContext,
    ) -> HypothesisRetrievalRun:
        started = time.perf_counter()
        started_at = datetime.now(UTC)
        org_id = str(analysis_context.organization_id or "")
        analysis_id = str(analysis_context.analysis_run_id)
        project_id = str(analysis_context.options.get("project_id") or "") or None
        incident_id = str(analysis_context.incident_id) if analysis_context.incident_id else None

        run = HypothesisRetrievalRun(
            organization_id=org_id,
            analysis_id=analysis_id,
            project_id=project_id,
            incident_id=incident_id,
            status=HypothesisRetrievalRunStatus.PENDING,
            execution_mode=RetrievalExecutionMode.DISABLED,
            started_at=started_at,
            configuration_snapshot=self._configuration_snapshot(),
            embedding_model_version=self._settings.embedding_model,
            retrieval_pipeline_version=RETRIEVAL_PIPELINE_VERSION,
        )

        if not self._settings.hypothesis_directed_rag_enabled or not org_id:
            run.status = HypothesisRetrievalRunStatus.DISABLED
            run.completed_at = datetime.now(UTC)
            run.duration_ms = int((time.perf_counter() - started) * 1000)
            run.warnings.append("hypothesis_directed_rag_disabled")
            return run

        # Never call causal_ranking_enabled — reserved for Phase 6A.6+.
        self._hybrid.bind_analysis_context(analysis_context)

        try:
            hyp_run, eligible = await self._load_eligible_hypotheses(
                db, organization_id=org_id, analysis_id=analysis_id
            )
        except Exception as exc:  # noqa: BLE001
            run.status = HypothesisRetrievalRunStatus.FAILED
            run.error_summary = type(exc).__name__
            run.warnings.append(f"load_hypotheses_failed:{type(exc).__name__}")
            run.completed_at = datetime.now(UTC)
            run.duration_ms = int((time.perf_counter() - started) * 1000)
            return run

        if hyp_run is not None:
            run.hypothesis_generation_run_id = str(hyp_run.id)

        run.hypothesis_count_requested = len(eligible)
        if not eligible:
            run.status = HypothesisRetrievalRunStatus.NO_EVIDENCE
            run.warnings.append("no_eligible_hypotheses")
            run.completed_at = datetime.now(UTC)
            run.duration_ms = int((time.perf_counter() - started) * 1000)
            if self._settings.hypothesis_retrieval_persistence_enabled:
                await HypothesisRetrievalPersistService(db).persist(run)
            return run

        run.status = HypothesisRetrievalRunStatus.RUNNING
        run.execution_mode = (
            RetrievalExecutionMode.MULTI_QUERY
            if self._settings.multi_query_retrieval_enabled
            else RetrievalExecutionMode.SINGLE_QUERY
        )

        # Phase A — sequential context builds (AsyncSession is not concurrency-safe).
        prepared: list[tuple[HypothesisRetrievalSession, HypothesisRetrievalContext]] = []
        builder = HypothesisRetrievalContextBuilder(
            db,
            max_context_chars=self._settings.max_retrieval_context_chars,
            max_graph_nodes=self._settings.max_graph_context_nodes_for_retrieval,
            max_graph_edges=self._settings.max_graph_context_edges_for_retrieval,
            max_artifact_evidence=self._settings.max_artifact_evidence_items_for_retrieval,
        )
        signals = dict(analysis_context.signals or {})
        for hyp, critic in eligible:
            session = HypothesisRetrievalSession(
                organization_id=org_id,
                analysis_id=analysis_id,
                hypothesis_id=str(hyp.id),
                hypothesis_key=hyp.hypothesis_key,
                project_id=project_id or (str(hyp.project_id) if hyp.project_id else None),
                incident_id=incident_id or (str(hyp.incident_id) if hyp.incident_id else None),
                status=HypothesisRetrievalSessionStatus.PENDING,
                execution_mode=run.execution_mode,
                hypothesis_prior_score_snapshot=float(hyp.generation_prior_score or 0.0),
                category_code=hyp.category_code,
                causal_claim_snapshot=hyp.causal_claim,
                affected_artifact_id=hyp.affected_artifact_id,
                root_cause_node_id=hyp.root_cause_node_id,
                observed_failure_node_id=hyp.observed_failure_node_id,
                started_at=datetime.now(UTC),
            )
            try:
                ctx = await builder.build(
                    organization_id=org_id,
                    analysis_id=analysis_id,
                    hypothesis_id=str(hyp.id),
                    project_id=session.project_id,
                    signals=signals,
                )
                if critic is not None:
                    ctx.critic_decision = critic.decision
                session.context = ctx
                session.status = HypothesisRetrievalSessionStatus.PLANNED
                prepared.append((session, ctx))
            except Exception as exc:  # noqa: BLE001
                session.status = HypothesisRetrievalSessionStatus.FAILED
                session.errors.append(type(exc).__name__)
                session.warnings.append(f"context_build_failed:{type(exc).__name__}")
                session.completed_at = datetime.now(UTC)
                session.duration_ms = 0
                prepared.append((session, HypothesisRetrievalContext(
                    analysis_id=analysis_id,
                    organization_id=org_id,
                    incident_id=session.incident_id,
                    hypothesis_id=str(hyp.id),
                    hypothesis_key=hyp.hypothesis_key,
                )))

        # Phase B — bounded-concurrent adapter execution (no shared DB writes).
        semaphore = asyncio.Semaphore(
            max(1, self._settings.max_concurrent_hypothesis_retrieval_sessions)
        )
        timeout = float(self._settings.hypothesis_retrieval_timeout_seconds)

        async def _execute(session: HypothesisRetrievalSession, ctx: HypothesisRetrievalContext):
            async with semaphore:
                if session.status == HypothesisRetrievalSessionStatus.FAILED:
                    return session
                return await asyncio.to_thread(self._execute_session_sync, session, ctx)

        tasks = [
            asyncio.create_task(_execute(session, ctx)) for session, ctx in prepared
        ]
        sessions: list[HypothesisRetrievalSession] = []
        timed_out = False
        done, pending = await asyncio.wait(
            tasks, timeout=timeout, return_when=asyncio.ALL_COMPLETED
        )
        for task in pending:
            timed_out = True
            task.cancel()
        for task in pending:
            with contextlib.suppress(asyncio.CancelledError):
                await task
            # Mark corresponding unfinished sessions as timed out.
        completed_ids = set()
        for task in done:
            try:
                sess = task.result()
                sessions.append(sess)
                completed_ids.add(sess.hypothesis_id)
            except Exception as exc:  # noqa: BLE001
                run.warnings.append(f"session_task_failed:{type(exc).__name__}")

        if timed_out:
            for session, _ctx in prepared:
                if session.hypothesis_id not in completed_ids:
                    session.status = HypothesisRetrievalSessionStatus.TIMED_OUT
                    session.warnings.append("session_cancelled_on_overall_timeout")
                    session.completed_at = datetime.now(UTC)
                    sessions.append(session)

        sessions.sort(key=lambda s: s.hypothesis_key)
        run.sessions = sessions
        run.hypothesis_count_processed = len(sessions)
        self._finalize_run_metrics(run, timed_out=timed_out)
        run.completed_at = datetime.now(UTC)
        run.duration_ms = int((time.perf_counter() - started) * 1000)

        if self._settings.hypothesis_retrieval_persistence_enabled:
            try:
                await HypothesisRetrievalPersistService(db).persist(run)
            except Exception as exc:  # noqa: BLE001
                run.warnings.append(f"persist_failed:{type(exc).__name__}")
                if run.status == HypothesisRetrievalRunStatus.COMPLETE:
                    run.status = HypothesisRetrievalRunStatus.PARTIAL

        return run

    def _execute_session_sync(
        self,
        session: HypothesisRetrievalSession,
        ctx: HypothesisRetrievalContext,
    ) -> HypothesisRetrievalSession:
        started = time.perf_counter()
        try:
            plan = self._plan_builder.build(ctx, session_id=session.id)
            session.plan = plan
            session.execution_mode = plan.execution_mode
            session.query_count = len(plan.query_specs)
            # Keep informational plan notes on the plan snapshot only.
            significant_plan_warnings = [
                w
                for w in plan.warnings
                if w.startswith("rejected_secret_like:") or w.startswith("rejected_oversized:")
            ]
            session.warnings.extend(significant_plan_warnings)

            if not plan.query_specs:
                session.status = HypothesisRetrievalSessionStatus.NO_EVIDENCE
                session.warnings.append("empty_retrieval_plan")
                session.completed_at = datetime.now(UTC)
                session.duration_ms = int((time.perf_counter() - started) * 1000)
                return session

            session.status = HypothesisRetrievalSessionStatus.RETRIEVING
            all_items: list[HypothesisRetrievedItem] = []
            query_executions: list[HypothesisRetrievalQueryExecution] = []
            attempted: set[str] = set()
            succeeded: set[str] = set()
            unavailable: set[str] = set()
            cache_hits = 0
            adapter_calls = 0
            failed_adapters = 0

            for spec in plan.query_specs:
                q_started = datetime.now(UTC)
                q_t0 = time.perf_counter()
                adapters = self._adapters_for_sources(spec.source_types)
                adapters_attempted: list[str] = []
                adapters_succeeded: list[str] = []
                raw_count = 0
                accepted: list[HypothesisRetrievedItem] = []
                warnings: list[str] = []
                errors: list[str] = []
                failure_type: RetrievalFailureType | None = None
                any_cache = False
                q_status = "COMPLETE"

                if not adapters:
                    q_status = "SOURCE_UNAVAILABLE"
                    failure_type = RetrievalFailureType.SOURCE_UNAVAILABLE
                    for src in spec.source_types:
                        unavailable.add(src.value)
                    errors.append("no_adapters_for_source_types")
                else:
                    for adapter in adapters:
                        adapter_calls += 1
                        adapters_attempted.append(adapter.adapter_name)
                        for src in adapter.supported_source_types:
                            attempted.add(src.value)
                        if not adapter.is_available():
                            unavailable.update(s.value for s in adapter.supported_source_types)
                            warnings.append(f"unavailable:{adapter.adapter_name}")
                            continue
                        result = adapter.retrieve(ctx, spec)
                        if result.cache_hit:
                            any_cache = True
                            cache_hits += 1
                        if result.status in {"FAILED", "SOURCE_UNAVAILABLE"}:
                            failed_adapters += 1
                            errors.extend(result.errors)
                            if result.failure_type:
                                failure_type = result.failure_type
                            if result.status == "SOURCE_UNAVAILABLE":
                                unavailable.update(
                                    s.value for s in adapter.supported_source_types
                                )
                            continue
                        adapters_succeeded.append(adapter.adapter_name)
                        succeeded.update(s.value for s in adapter.supported_source_types)
                        raw_count += result.raw_result_count
                        accepted.extend(result.items)
                        warnings.extend(result.warnings)

                if not accepted and q_status == "COMPLETE":
                    q_status = "NO_EVIDENCE" if not errors else "FAILED"
                    if errors and failure_type is None:
                        failure_type = RetrievalFailureType.INTERNAL_ERROR

                all_items.extend(accepted)
                query_executions.append(
                    HypothesisRetrievalQueryExecution(
                        query_id=spec.query_id,
                        query_type=spec.query_type,
                        normalized_query=spec.normalized_query,
                        source_types=list(spec.source_types),
                        status=q_status,
                        adapters_attempted=adapters_attempted,
                        adapters_succeeded=adapters_succeeded,
                        raw_result_count=raw_count,
                        accepted_result_count=len(accepted),
                        cache_hit=any_cache,
                        started_at=q_started,
                        completed_at=datetime.now(UTC),
                        duration_ms=int((time.perf_counter() - q_t0) * 1000),
                        failure_type=failure_type,
                        warnings=warnings,
                        error_summary=";".join(errors[:5]) if errors else None,
                    )
                )

            deduped, duplicate_count = deduplicate_session_items(all_items)
            max_items = self._settings.max_retrieved_items_per_hypothesis
            if len(deduped) > max_items:
                deduped = deduped[:max_items]
                session.warnings.append(f"bounded_items:{max_items}")

            session.query_executions = query_executions
            session.items = deduped
            session.raw_result_count = sum(q.raw_result_count for q in query_executions)
            session.accepted_result_count = len(deduped)
            session.unique_source_count = len(
                {
                    (
                        i.source_type.value,
                        i.source_id or i.chunk_id or i.document_id or i.normalized_text_hash,
                    )
                    for i in deduped
                }
            )
            session.cache_hit_count = cache_hits
            session.source_types_attempted = sorted(attempted)
            session.source_types_succeeded = sorted(succeeded)
            session.source_types_unavailable = sorted(unavailable)
            session.metrics = {
                "adapter_call_count": adapter_calls,
                "failed_adapters": failed_adapters,
                "duplicate_count": duplicate_count,
                "context_size": ctx.final_size or ctx.total_character_count,
                "plan_size": len(plan.query_specs),
                "average_retrieval_score": (
                    sum(i.retrieval_score for i in deduped) / len(deduped) if deduped else 0.0
                ),
                "maximum_retrieval_score": max((i.retrieval_score for i in deduped), default=0.0),
                "source_counts_by_type": _count_by_source(deduped),
                "truncation_count": 1 if ctx.was_truncated else 0,
            }

            failed_queries = sum(1 for q in query_executions if q.status == "FAILED")
            no_evidence_queries = sum(1 for q in query_executions if q.status == "NO_EVIDENCE")
            if failed_queries == len(query_executions):
                session.status = HypothesisRetrievalSessionStatus.FAILED
            elif not deduped and (unavailable or no_evidence_queries == len(query_executions)):
                session.status = HypothesisRetrievalSessionStatus.NO_EVIDENCE
            elif failed_queries or unavailable:
                session.status = HypothesisRetrievalSessionStatus.PARTIAL
            else:
                session.status = HypothesisRetrievalSessionStatus.COMPLETE
        except Exception as exc:  # noqa: BLE001
            session.status = HypothesisRetrievalSessionStatus.FAILED
            session.errors.append(type(exc).__name__)
            session.warnings.append(f"session_failed:{type(exc).__name__}")

        session.completed_at = datetime.now(UTC)
        session.duration_ms = int((time.perf_counter() - started) * 1000)
        return session

    async def _load_eligible_hypotheses(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        analysis_id: str,
    ) -> tuple[
        CausalHypothesisRunRow | None,
        list[tuple[CausalHypothesisRow, HypothesisCriticResultRow | None]],
    ]:
        org_uuid = UUID(organization_id)
        analysis_uuid = UUID(analysis_id)
        hyp_run = await db.scalar(
            select(CausalHypothesisRunRow).where(
                CausalHypothesisRunRow.organization_id == org_uuid,
                CausalHypothesisRunRow.analysis_run_id == analysis_uuid,
            )
        )
        if hyp_run is None:
            return None, []

        hyps = list(
            (
                await db.scalars(
                    select(CausalHypothesisRow)
                    .where(
                        CausalHypothesisRow.hypothesis_run_id == hyp_run.id,
                        CausalHypothesisRow.organization_id == org_uuid,
                    )
                    .order_by(
                        CausalHypothesisRow.generation_prior_score.desc(),
                        CausalHypothesisRow.rank_placeholder.asc(),
                        CausalHypothesisRow.hypothesis_key.asc(),
                    )
                )
            ).all()
        )
        if not hyps:
            return hyp_run, []

        hyp_ids = [h.id for h in hyps]
        critics = list(
            (
                await db.scalars(
                    select(HypothesisCriticResultRow).where(
                        HypothesisCriticResultRow.hypothesis_id.in_(hyp_ids)
                    )
                )
            ).all()
        )
        critic_by_hyp = {c.hypothesis_id: c for c in critics}

        eligible: list[tuple[CausalHypothesisRow, HypothesisCriticResultRow | None]] = []
        for hyp in hyps:
            critic = critic_by_hyp.get(hyp.id)
            if is_hypothesis_eligible_for_retrieval(
                status=hyp.status,
                critic_decision=critic.decision if critic else None,
                missing_evidence=list(hyp.missing_evidence or []),
            ):
                eligible.append((hyp, critic))

        return hyp_run, eligible[: self._settings.max_hypotheses_for_retrieval]

    def _adapters_for_sources(self, source_types: list[HypothesisRetrievalSourceType]) -> list[Any]:
        adapters: list[Any] = []
        types = set(source_types)
        if HypothesisRetrievalSourceType.ARTIFACT in types:
            adapters.append(self._artifact)
        if HypothesisRetrievalSourceType.GRAPH in types:
            adapters.append(self._graph)
        if HypothesisRetrievalSourceType.TEMPORAL in types:
            adapters.append(self._temporal)
        if types & {
            HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
            HypothesisRetrievalSourceType.VECTOR_KNOWLEDGE,
            HypothesisRetrievalSourceType.LEXICAL_KNOWLEDGE,
            HypothesisRetrievalSourceType.HISTORICAL_INCIDENT,
        }:
            adapters.append(self._hybrid)
        order = {
            self._artifact.adapter_name: 1,
            self._graph.adapter_name: 2,
            self._temporal.adapter_name: 3,
            self._hybrid.adapter_name: 4,
        }
        adapters.sort(key=lambda a: (order.get(a.adapter_name, 99), a.adapter_name))
        return adapters

    def _configuration_snapshot(self) -> dict[str, Any]:
        s = self._settings
        return {
            "hypothesis_directed_rag_enabled": s.hypothesis_directed_rag_enabled,
            "multi_query_retrieval_enabled": s.multi_query_retrieval_enabled,
            "hypothesis_graph_context_enabled": s.hypothesis_graph_context_enabled,
            "hypothesis_historical_retrieval_enabled": s.hypothesis_historical_retrieval_enabled,
            "hypothesis_static_kb_retrieval_enabled": s.hypothesis_static_kb_retrieval_enabled,
            "hypothesis_artifact_retrieval_enabled": s.hypothesis_artifact_retrieval_enabled,
            "hypothesis_retrieval_persistence_enabled": s.hypothesis_retrieval_persistence_enabled,
            "retrieval_cache_enabled": s.retrieval_cache_enabled,
            "max_hypotheses_for_retrieval": s.max_hypotheses_for_retrieval,
            "max_queries_per_hypothesis": s.max_queries_per_hypothesis,
            "max_results_per_query": s.max_results_per_query,
            "max_retrieved_items_per_hypothesis": s.max_retrieved_items_per_hypothesis,
            "max_concurrent_hypothesis_retrieval_sessions": (
                s.max_concurrent_hypothesis_retrieval_sessions
            ),
            "hypothesis_retrieval_timeout_seconds": s.hypothesis_retrieval_timeout_seconds,
            "retrieval_pipeline_version": RETRIEVAL_PIPELINE_VERSION,
            "causal_ranking_enabled_unused": s.causal_ranking_enabled,
        }

    def _finalize_run_metrics(self, run: HypothesisRetrievalRun, *, timed_out: bool) -> None:
        complete = partial = failed = no_evidence = 0
        total_queries = 0
        total_results = 0
        unique_sources = 0
        for sess in run.sessions:
            total_queries += sess.query_count
            total_results += sess.accepted_result_count
            unique_sources += sess.unique_source_count
            if sess.status == HypothesisRetrievalSessionStatus.COMPLETE:
                complete += 1
            elif sess.status == HypothesisRetrievalSessionStatus.PARTIAL:
                partial += 1
            elif sess.status in {
                HypothesisRetrievalSessionStatus.FAILED,
                HypothesisRetrievalSessionStatus.TIMED_OUT,
            }:
                failed += 1
            elif sess.status == HypothesisRetrievalSessionStatus.NO_EVIDENCE:
                no_evidence += 1

        run.session_count_complete = complete
        run.session_count_partial = partial
        run.session_count_failed = failed
        run.total_query_count = total_queries
        run.total_result_count = total_results
        run.total_unique_source_count = unique_sources

        if timed_out:
            run.status = HypothesisRetrievalRunStatus.TIMED_OUT
            run.warnings.append("overall_timeout")
            return
        if not run.sessions:
            run.status = HypothesisRetrievalRunStatus.NO_EVIDENCE
            return
        if failed == len(run.sessions):
            run.status = HypothesisRetrievalRunStatus.FAILED
            return
        if complete == len(run.sessions) and not run.warnings:
            run.status = HypothesisRetrievalRunStatus.COMPLETE
            return
        if total_results == 0 and (no_evidence + failed) == len(run.sessions):
            run.status = HypothesisRetrievalRunStatus.NO_EVIDENCE
            return
        if partial or failed or no_evidence or run.warnings:
            run.status = HypothesisRetrievalRunStatus.PARTIAL
            return
        run.status = HypothesisRetrievalRunStatus.COMPLETE


def _count_by_source(items: list[HypothesisRetrievedItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = item.source_type.value
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))
