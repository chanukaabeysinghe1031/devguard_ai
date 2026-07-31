"""Hypothesis-directed retrieval orchestrator (Phase 6A.5 Part 1B + Part 2)."""

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
from app.ai.hypothesis_retrieval.adapters.repository import RepositoryChangeRetrievalAdapter
from app.ai.hypothesis_retrieval.adapters.temporal import TemporalEvidenceRetrievalAdapter
from app.ai.hypothesis_retrieval.adaptive_planner import AdaptiveHypothesisRetrievalPlanner
from app.ai.hypothesis_retrieval.cache import InMemoryRetrievalCache
from app.ai.hypothesis_retrieval.context_builder import HypothesisRetrievalContextBuilder
from app.ai.hypothesis_retrieval.dedupe import deduplicate_session_items
from app.ai.hypothesis_retrieval.features import RetrievalCandidateFeatureExtractor
from app.ai.hypothesis_retrieval.follow_up import HypothesisRetrievalFollowUpPlanner
from app.ai.hypothesis_retrieval.persist import HypothesisRetrievalPersistService
from app.ai.hypothesis_retrieval.plan_builder import HypothesisRetrievalPlanBuilder
from app.ai.hypothesis_retrieval.relevance import HypothesisRetrievalRelevanceScorer
from app.ai.hypothesis_retrieval.validator import RetrievalResultValidator
from app.ai.hypothesis_retrieval.versions import (
    ADAPTIVE_RETRIEVAL_PLANNER_VERSION,
    PLAN_VERSION_V2,
    RETRIEVAL_PIPELINE_VERSION_V2,
)
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
    RetrievalValidationStatus,
)
from app.domain.hypothesis_retrieval.models import (
    PLAN_VERSION,
    RETRIEVAL_PIPELINE_VERSION,
    AdaptiveHypothesisRetrievalPlan,
    HypothesisRetrievalContext,
    HypothesisRetrievalPlan,
    HypothesisRetrievalQueryExecution,
    HypothesisRetrievalQuerySpec,
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
        self._repository = RepositoryChangeRetrievalAdapter(enabled=True)
        self._hybrid = HybridPipelineHypothesisAdapter(
            hybrid_pipeline,
            cache=self._cache,
            cache_enabled=settings.retrieval_cache_enabled,
            embedding_model_version=settings.embedding_model,
            historical_enabled=settings.hypothesis_historical_retrieval_enabled,
            static_kb_enabled=settings.hypothesis_static_kb_retrieval_enabled,
            metadata_filtering_enabled=settings.hypothesis_metadata_filtering_enabled,
            exact_identifier_boost_enabled=settings.hypothesis_exact_identifier_boost_enabled,
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
        self._adaptive_planner = AdaptiveHypothesisRetrievalPlanner(
            max_total_queries=settings.max_total_queries_per_hypothesis,
            max_expansions=settings.max_query_expansions_per_hypothesis,
            max_identifiers=settings.max_exact_identifiers_per_query,
            max_source_types=settings.max_source_types_per_query,
            follow_up_limit=settings.max_follow_up_rounds,
            expansion_enabled=settings.hypothesis_query_expansion_enabled,
            source_routing_enabled=settings.hypothesis_source_routing_enabled,
            artifact_enabled=settings.hypothesis_artifact_retrieval_enabled,
            graph_enabled=settings.hypothesis_graph_context_enabled,
            historical_enabled=settings.hypothesis_historical_retrieval_enabled,
            static_kb_enabled=settings.hypothesis_static_kb_retrieval_enabled,
            max_graph_depth=settings.max_graph_retrieval_depth,
            max_graph_nodes=settings.max_graph_retrieval_nodes,
            max_graph_edges=settings.max_graph_retrieval_edges,
            max_artifact_results=settings.max_artifact_results_per_query,
            max_temporal_results=settings.max_temporal_results_per_query,
            timeout_seconds=settings.hypothesis_retrieval_timeout_seconds,
            top_k=settings.max_results_per_query,
            max_query_chars=settings.max_retrieval_query_chars,
        )
        self._validator = RetrievalResultValidator(
            max_items=settings.max_retrieval_validation_items
        )
        self._features = RetrievalCandidateFeatureExtractor()
        self._relevance = HypothesisRetrievalRelevanceScorer(
            exact_identifier_boost_enabled=settings.hypothesis_exact_identifier_boost_enabled,
        )
        self._follow_up = HypothesisRetrievalFollowUpPlanner(
            min_results=settings.min_results_before_follow_up,
            min_relevance=settings.min_retrieval_score_for_acceptance,
            max_rounds=settings.max_follow_up_rounds,
            max_query_chars=settings.max_retrieval_query_chars,
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

        pipeline_version = (
            RETRIEVAL_PIPELINE_VERSION_V2
            if self._settings.adaptive_hypothesis_retrieval_enabled
            else RETRIEVAL_PIPELINE_VERSION
        )
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
            retrieval_pipeline_version=pipeline_version,
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
            or self._settings.adaptive_hypothesis_retrieval_enabled
            else RetrievalExecutionMode.SINGLE_QUERY
        )

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
                prepared.append(
                    (
                        session,
                        HypothesisRetrievalContext(
                            analysis_id=analysis_id,
                            organization_id=org_id,
                            incident_id=session.incident_id,
                            hypothesis_id=str(hyp.id),
                            hypothesis_key=hyp.hypothesis_key,
                        ),
                    )
                )

        semaphore = asyncio.Semaphore(
            max(1, self._settings.max_concurrent_hypothesis_retrieval_sessions)
        )
        timeout = float(
            min(
                self._settings.hypothesis_retrieval_timeout_seconds,
                self._settings.max_retrieval_total_duration_seconds,
            )
        )

        async def _execute(session: HypothesisRetrievalSession, ctx: HypothesisRetrievalContext):
            async with semaphore:
                if session.status == HypothesisRetrievalSessionStatus.FAILED:
                    return session
                return await asyncio.to_thread(self._execute_session_sync, session, ctx)

        tasks = [asyncio.create_task(_execute(session, ctx)) for session, ctx in prepared]
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
            basic_plan = self._plan_builder.build(ctx, session_id=session.id)
            adaptive_plan: AdaptiveHypothesisRetrievalPlan | None = None
            plan: HypothesisRetrievalPlan = basic_plan

            if self._settings.adaptive_hypothesis_retrieval_enabled:
                adaptive_plan = self._adaptive_planner.plan(
                    ctx, basic_plan, session_id=session.id
                )
                plan = HypothesisRetrievalPlan(
                    hypothesis_id=ctx.hypothesis_id,
                    session_id=session.id,
                    execution_mode=basic_plan.execution_mode,
                    plan_version=PLAN_VERSION_V2,
                    query_specs=list(adaptive_plan.query_specs),
                    enabled_source_types=list(adaptive_plan.enabled_source_types),
                    excluded_source_types=list(adaptive_plan.excluded_source_types),
                    graph_constraints=(
                        adaptive_plan.graph_constraints.to_dict()
                        if adaptive_plan.graph_constraints
                        else {}
                    ),
                    artifact_constraints=(
                        adaptive_plan.artifact_constraints.to_dict()
                        if adaptive_plan.artifact_constraints
                        else {}
                    ),
                    repository_constraints=dict(adaptive_plan.repository_constraints),
                    time_constraints=(
                        adaptive_plan.temporal_constraints.to_dict()
                        if adaptive_plan.temporal_constraints
                        else {}
                    ),
                    result_limits=dict(basic_plan.result_limits),
                    timeout_seconds=adaptive_plan.timeout_seconds,
                    cache_policy=dict(basic_plan.cache_policy),
                    warnings=list(adaptive_plan.planning_warnings),
                    plan_key=basic_plan.plan_key,
                )
                session.plan = plan
                session.retrieval_plan_version = PLAN_VERSION_V2
            else:
                session.plan = plan
                session.retrieval_plan_version = plan.plan_version or PLAN_VERSION

            session.execution_mode = plan.execution_mode
            session.query_count = len(plan.query_specs)
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
            exec_state = self._run_queries(session, ctx, list(plan.query_specs), follow_up_round=0)
            follow_payload: dict[str, Any] | None = None

            if (
                self._settings.adaptive_hypothesis_retrieval_enabled
                and self._settings.retrieval_follow_up_enabled
            ):
                follow = self._follow_up.plan(
                    ctx,
                    accepted_items=exec_state["accepted_items"],
                    existing_specs=list(plan.query_specs),
                    required_source_types=(
                        list(adaptive_plan.required_source_types) if adaptive_plan else []
                    ),
                    current_round=0,
                    max_relevance=exec_state.get("max_relevance"),
                    had_exact_identifier_match=bool(
                        exec_state.get("had_exact_identifier_match")
                    ),
                )
                follow_payload = follow.to_dict()
                if follow.should_follow_up and follow.follow_up_specs:
                    before_count = len(exec_state["accepted_items"])
                    exec_state = self._run_queries(
                        session,
                        ctx,
                        follow.follow_up_specs,
                        follow_up_round=1,
                        seed_items=exec_state["all_items"],
                        seed_executions=exec_state["query_executions"],
                        seed_attempted=exec_state["attempted"],
                        seed_succeeded=exec_state["succeeded"],
                        seed_unavailable=exec_state["unavailable"],
                        seed_cache_hits=exec_state["cache_hits"],
                        seed_adapter_calls=exec_state["adapter_calls"],
                        seed_failed_adapters=exec_state["failed_adapters"],
                    )
                    follow_payload["follow_up_result_count"] = (
                        len(exec_state["accepted_items"]) - before_count
                    )

            all_items = exec_state["all_items"]
            query_executions = exec_state["query_executions"]
            attempted = exec_state["attempted"]
            succeeded = exec_state["succeeded"]
            unavailable = exec_state["unavailable"]
            cache_hits = exec_state["cache_hits"]
            adapter_calls = exec_state["adapter_calls"]
            failed_adapters = exec_state["failed_adapters"]

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

            metrics: dict[str, Any] = {
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
            if adaptive_plan is not None:
                metrics["intelligence"] = {
                    "planner_version": ADAPTIVE_RETRIEVAL_PLANNER_VERSION,
                    "intents": [i.to_dict() for i in adaptive_plan.intents],
                    "routing": [
                        (s.metadata or {}).get("routing")
                        for s in adaptive_plan.query_specs
                        if (s.metadata or {}).get("routing")
                    ],
                    "follow_up": follow_payload,
                    "relevance_summary": exec_state.get("relevance_summary"),
                    "validation_summary": exec_state.get("validation_summary"),
                    "identifiers_count": len(
                        (adaptive_plan.metadata_constraints or {}).get("identifiers") or []
                    ),
                    "adaptive_plan_version": PLAN_VERSION_V2,
                    "planning_decisions": list(adaptive_plan.planning_decisions),
                    "was_downgraded": adaptive_plan.was_downgraded,
                    "downgrade_reason": adaptive_plan.downgrade_reason,
                }
                metrics["adaptive_plan"] = adaptive_plan.to_dict()
            session.metrics = metrics

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

    def _run_queries(
        self,
        session: HypothesisRetrievalSession,
        ctx: HypothesisRetrievalContext,
        specs: list[HypothesisRetrievalQuerySpec],
        *,
        follow_up_round: int,
        seed_items: list[HypothesisRetrievedItem] | None = None,
        seed_executions: list[HypothesisRetrievalQueryExecution] | None = None,
        seed_attempted: set[str] | None = None,
        seed_succeeded: set[str] | None = None,
        seed_unavailable: set[str] | None = None,
        seed_cache_hits: int = 0,
        seed_adapter_calls: int = 0,
        seed_failed_adapters: int = 0,
    ) -> dict[str, Any]:
        del session  # session mutated by caller after aggregation
        all_items: list[HypothesisRetrievedItem] = list(seed_items or [])
        query_executions: list[HypothesisRetrievalQueryExecution] = list(
            seed_executions or []
        )
        attempted: set[str] = set(seed_attempted or set())
        succeeded: set[str] = set(seed_succeeded or set())
        unavailable: set[str] = set(seed_unavailable or set())
        cache_hits = seed_cache_hits
        adapter_calls = seed_adapter_calls
        failed_adapters = seed_failed_adapters

        identifiers = None
        if self._settings.adaptive_hypothesis_retrieval_enabled:
            identifiers = self._adaptive_planner.extract_identifiers(ctx)

        validation_summary: dict[str, int] = {}
        relevance_scores: list[float] = []
        had_exact = False

        for spec in specs:
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

            processed: list[HypothesisRetrievedItem] = []
            if self._settings.adaptive_hypothesis_retrieval_enabled:
                seen_keys: set[str] = set()
                for item in accepted:
                    item_meta = dict(item.metadata or {})
                    item_meta["follow_up_round"] = follow_up_round
                    intent_ids = []
                    if (spec.metadata or {}).get("intent_id"):
                        intent_ids.append(str(spec.metadata["intent_id"]))
                    item_meta["intent_ids"] = intent_ids

                    if self._settings.retrieval_result_validation_enabled:
                        validation = self._validator.validate(
                            item, ctx, seen_keys=seen_keys
                        )
                        item_meta["validation_status"] = validation.status.value
                        validation_summary[validation.status.value] = (
                            validation_summary.get(validation.status.value, 0) + 1
                        )
                        if not RetrievalResultValidator.is_accepted(validation.status):
                            item.metadata = item_meta
                            continue
                        if validation.status == RetrievalValidationStatus.ACCEPTED_WITH_WARNINGS:
                            item_meta["validation_warnings"] = list(validation.warnings)

                    features = self._features.extract(item, ctx, identifiers)
                    item_meta["features"] = features.to_dict()
                    assessment = self._relevance.score(
                        item_id=item.source_id
                        or item.normalized_text_hash
                        or item.query_id,
                        features=features,
                        retrieval_score=item.retrieval_score,
                    )
                    item_meta["retrieval_relevance_score"] = (
                        assessment.retrieval_relevance_score
                    )
                    relevance_scores.append(assessment.retrieval_relevance_score)
                    exact_matches = []
                    if identifiers:
                        text_l = (item.text_excerpt or "").lower()
                        exact_matches = [
                            i for i in identifiers.all_identifiers if i.lower() in text_l
                        ]
                        if exact_matches:
                            had_exact = True
                    item_meta["exact_identifier_matches"] = exact_matches
                    item.metadata = item_meta
                    processed.append(item)
            else:
                processed = accepted

            if not processed and q_status == "COMPLETE":
                q_status = "NO_EVIDENCE" if not errors else "FAILED"
                if errors and failure_type is None:
                    failure_type = RetrievalFailureType.INTERNAL_ERROR

            all_items.extend(processed)
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
                    accepted_result_count=len(processed),
                    cache_hit=any_cache,
                    started_at=q_started,
                    completed_at=datetime.now(UTC),
                    duration_ms=int((time.perf_counter() - q_t0) * 1000),
                    failure_type=failure_type,
                    warnings=warnings,
                    error_summary=";".join(errors[:5]) if errors else None,
                )
            )

        def _sort_key(item: HypothesisRetrievedItem) -> float:
            meta = item.metadata or {}
            if "retrieval_relevance_score" in meta:
                return float(meta["retrieval_relevance_score"])
            return float(item.retrieval_score)

        all_items_sorted = sorted(all_items, key=_sort_key, reverse=True)
        return {
            "all_items": all_items_sorted,
            "accepted_items": all_items_sorted,
            "query_executions": query_executions,
            "attempted": attempted,
            "succeeded": succeeded,
            "unavailable": unavailable,
            "cache_hits": cache_hits,
            "adapter_calls": adapter_calls,
            "failed_adapters": failed_adapters,
            "max_relevance": max(relevance_scores) if relevance_scores else None,
            "had_exact_identifier_match": had_exact,
            "validation_summary": validation_summary,
            "relevance_summary": {
                "count": len(relevance_scores),
                "max": max(relevance_scores) if relevance_scores else 0.0,
                "avg": (
                    sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
                ),
            },
        }

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
        if HypothesisRetrievalSourceType.REPOSITORY_CHANGE in types:
            adapters.append(self._repository)
        if types & {
            HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
            HypothesisRetrievalSourceType.VECTOR_KNOWLEDGE,
            HypothesisRetrievalSourceType.LEXICAL_KNOWLEDGE,
            HypothesisRetrievalSourceType.HISTORICAL_INCIDENT,
            HypothesisRetrievalSourceType.DOCUMENTATION,
        }:
            adapters.append(self._hybrid)
        order = {
            self._artifact.adapter_name: 1,
            self._graph.adapter_name: 2,
            self._temporal.adapter_name: 3,
            self._repository.adapter_name: 4,
            self._hybrid.adapter_name: 5,
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
            "adaptive_hypothesis_retrieval_enabled": s.adaptive_hypothesis_retrieval_enabled,
            "hypothesis_query_expansion_enabled": s.hypothesis_query_expansion_enabled,
            "hypothesis_source_routing_enabled": s.hypothesis_source_routing_enabled,
            "retrieval_result_validation_enabled": s.retrieval_result_validation_enabled,
            "retrieval_follow_up_enabled": s.retrieval_follow_up_enabled,
            "hypothesis_exact_identifier_boost_enabled": (
                s.hypothesis_exact_identifier_boost_enabled
            ),
            "hypothesis_metadata_filtering_enabled": s.hypothesis_metadata_filtering_enabled,
            "max_hypotheses_for_retrieval": s.max_hypotheses_for_retrieval,
            "max_queries_per_hypothesis": s.max_queries_per_hypothesis,
            "max_total_queries_per_hypothesis": s.max_total_queries_per_hypothesis,
            "max_results_per_query": s.max_results_per_query,
            "max_retrieved_items_per_hypothesis": s.max_retrieved_items_per_hypothesis,
            "max_concurrent_hypothesis_retrieval_sessions": (
                s.max_concurrent_hypothesis_retrieval_sessions
            ),
            "hypothesis_retrieval_timeout_seconds": s.hypothesis_retrieval_timeout_seconds,
            "retrieval_pipeline_version": (
                RETRIEVAL_PIPELINE_VERSION_V2
                if s.adaptive_hypothesis_retrieval_enabled
                else RETRIEVAL_PIPELINE_VERSION
            ),
            "adaptive_retrieval_planner_version": ADAPTIVE_RETRIEVAL_PLANNER_VERSION,
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
