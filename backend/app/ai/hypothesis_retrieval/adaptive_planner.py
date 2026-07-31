"""Adaptive planner wrapping Part 1B plans without mutating them in place."""

from __future__ import annotations

from copy import deepcopy

from app.ai.hypothesis_retrieval.identifiers import (
    ExtractedIdentifiers,
    RetrievalIdentifierExtractor,
)
from app.ai.hypothesis_retrieval.intents import HypothesisQueryIntentGenerator
from app.ai.hypothesis_retrieval.query_deduplicator import HypothesisQueryDeduplicator
from app.ai.hypothesis_retrieval.query_generator import HypothesisSpecificQueryGenerator
from app.ai.hypothesis_retrieval.query_sanitizer import RetrievalQuerySanitizer
from app.ai.hypothesis_retrieval.source_router import HypothesisRetrievalSourceRouter
from app.ai.hypothesis_retrieval.versions import (
    ADAPTIVE_RETRIEVAL_PLANNER_VERSION,
    PLAN_VERSION_V2,
)
from app.domain.hypothesis_retrieval.enums import (
    EstimatedCostClass,
    HypothesisRetrievalSourceType,
)
from app.domain.hypothesis_retrieval.models import (
    PLAN_VERSION,
    AdaptiveHypothesisRetrievalPlan,
    ArtifactRetrievalConstraints,
    GraphRetrievalConstraints,
    HypothesisRetrievalContext,
    HypothesisRetrievalPlan,
    HypothesisRetrievalQuerySpec,
    TemporalRetrievalConstraints,
)


class AdaptiveHypothesisRetrievalPlanner:
    """Build an adaptive plan from a Part 1B plan; never mutates the basic plan."""

    def __init__(
        self,
        *,
        max_total_queries: int = 10,
        max_expansions: int = 4,
        max_identifiers: int = 8,
        max_source_types: int = 5,
        follow_up_limit: int = 1,
        expansion_enabled: bool = False,
        source_routing_enabled: bool = True,
        artifact_enabled: bool = True,
        graph_enabled: bool = False,
        historical_enabled: bool = True,
        static_kb_enabled: bool = True,
        max_graph_depth: int = 4,
        max_graph_nodes: int = 80,
        max_graph_edges: int = 150,
        max_artifact_results: int = 15,
        max_temporal_results: int = 15,
        timeout_seconds: float = 45.0,
        top_k: int = 10,
        max_query_chars: int = 2000,
    ) -> None:
        self._max_total = max(1, max_total_queries)
        self._follow_up_limit = max(1, follow_up_limit)
        self._expansion_enabled = expansion_enabled
        self._source_routing_enabled = source_routing_enabled
        self._timeout = timeout_seconds
        self._sanitizer = RetrievalQuerySanitizer(max_chars=max_query_chars)
        self._intent_gen = HypothesisQueryIntentGenerator()
        self._id_extractor = RetrievalIdentifierExtractor(max_identifiers=max_identifiers)
        self._query_gen = HypothesisSpecificQueryGenerator(
            sanitizer=self._sanitizer,
            max_expansions=max_expansions,
            max_identifiers=max_identifiers,
            top_k=top_k,
        )
        self._deduper = HypothesisQueryDeduplicator()
        self._router = HypothesisRetrievalSourceRouter(
            max_source_types=max_source_types,
            artifact_enabled=artifact_enabled,
            graph_enabled=graph_enabled,
            historical_enabled=historical_enabled,
            static_kb_enabled=static_kb_enabled,
        )
        self._graph_constraints = GraphRetrievalConstraints(
            max_depth=max_graph_depth,
            max_nodes=max_graph_nodes,
            max_edges=max_graph_edges,
        )
        self._artifact_constraints = ArtifactRetrievalConstraints(
            maximum_results=max_artifact_results
        )
        self._temporal_constraints = TemporalRetrievalConstraints(
            maximum_events=max_temporal_results
        )

    def plan(
        self,
        context: HypothesisRetrievalContext,
        basic_plan: HypothesisRetrievalPlan,
        *,
        session_id: str | None = None,
    ) -> AdaptiveHypothesisRetrievalPlan:
        basic_snapshot = deepcopy(basic_plan.to_dict())
        decisions: list[str] = []
        warnings: list[str] = []

        intents = self._intent_gen.generate(context, session_id=session_id)
        decisions.append(f"intents_generated:{len(intents)}")
        identifiers = self._id_extractor.extract(context)
        decisions.append(f"identifiers:{len(identifiers.all_identifiers)}")

        adaptive_specs = self._query_gen.generate(
            context,
            intents,
            identifiers,
            expansion_enabled=self._expansion_enabled,
        )
        decisions.append(f"adaptive_specs:{len(adaptive_specs)}")

        # Retain valid basic queries (copy, do not mutate).
        retained = [deepcopy(spec) for spec in basic_plan.query_specs]
        for spec in retained:
            meta = dict(spec.metadata or {})
            meta["from_basic_plan"] = True
            spec.metadata = meta
        decisions.append(f"retained_basic:{len(retained)}")

        merged = retained + adaptive_specs
        merged, dup_count = self._deduper.deduplicate(merged)
        if dup_count:
            warnings.append(f"deduplicated_queries:{dup_count}")

        routing_meta: list[dict] = []
        if self._source_routing_enabled:
            intent_by_id = {i.intent_id: i for i in intents}
            routed: list[HypothesisRetrievalQuerySpec] = []
            for spec in merged:
                intent_id = str((spec.metadata or {}).get("intent_id") or "")
                intent = intent_by_id.get(intent_id)
                decision = self._router.route(context, spec, intent)
                routing_meta.append(decision.to_dict())
                updated = deepcopy(spec)
                updated.source_types = list(decision.selected_sources) or list(
                    spec.source_types
                )
                meta = dict(updated.metadata or {})
                meta["routing"] = decision.to_dict()
                updated.metadata = meta
                routed.append(updated)
            merged = routed
            decisions.append("source_routing_applied")

        was_downgraded = False
        downgrade_reason = None
        if len(merged) > self._max_total:
            merged = merged[: self._max_total]
            was_downgraded = True
            downgrade_reason = f"capped_to_{self._max_total}"
            warnings.append(downgrade_reason)
            decisions.append("downgraded_query_cap")

        # Apply constraint hints onto specs metadata (soft).
        graph_c = deepcopy(self._graph_constraints)
        graph_c.start_node_ids = [
            n
            for n in (
                context.root_cause_node_id,
                context.observed_failure_node_id,
                *context.causal_path_node_ids,
            )
            if n
        ]
        artifact_c = deepcopy(self._artifact_constraints)
        if context.affected_artifact_id:
            artifact_c.artifact_ids = [context.affected_artifact_id]
        if context.affected_path:
            artifact_c.source_paths = [context.affected_path]
        artifact_c.failing_commit = context.commit_sha
        artifact_c.workflow_path = context.workflow_path
        temporal_c = deepcopy(self._temporal_constraints)
        temporal_c.primary_event_id = context.temporal_primary_event_id

        for spec in merged:
            meta = dict(spec.metadata or {})
            meta["graph_constraints"] = graph_c.to_dict()
            meta["artifact_constraints"] = artifact_c.to_dict()
            meta["temporal_constraints"] = temporal_c.to_dict()
            meta["identifiers"] = identifiers.to_dict()
            spec.metadata = meta

        enabled = sorted(
            {s for spec in merged for s in spec.source_types},
            key=lambda x: x.value,
        )
        return AdaptiveHypothesisRetrievalPlan(
            hypothesis_id=context.hypothesis_id,
            session_id=session_id,
            base_plan_version=basic_plan.plan_version or PLAN_VERSION,
            adaptive_plan_version=PLAN_VERSION_V2,
            intents=intents,
            query_specs=merged,
            enabled_source_types=enabled,
            required_source_types=[
                s for s in enabled if s in {HypothesisRetrievalSourceType.ARTIFACT}
            ],
            optional_source_types=[
                s for s in enabled if s != HypothesisRetrievalSourceType.ARTIFACT
            ],
            excluded_source_types=[],
            graph_constraints=graph_c,
            artifact_constraints=artifact_c,
            temporal_constraints=temporal_c,
            repository_constraints={
                "commit_sha": context.commit_sha,
                "changed_files": list(context.changed_files),
            },
            metadata_constraints={
                "category_code": context.category_code,
                "identifiers": identifiers.all_identifiers[:16],
            },
            total_query_limit=self._max_total,
            follow_up_limit=self._follow_up_limit,
            timeout_seconds=self._timeout,
            estimated_cost=EstimatedCostClass.MEDIUM,
            planning_warnings=warnings,
            planning_decisions=decisions,
            was_downgraded=was_downgraded,
            downgrade_reason=downgrade_reason,
            basic_plan_snapshot=basic_snapshot,
            planner_version=ADAPTIVE_RETRIEVAL_PLANNER_VERSION,
        )

    def extract_identifiers(
        self, context: HypothesisRetrievalContext
    ) -> ExtractedIdentifiers:
        return self._id_extractor.extract(context)
