"""Conservative deterministic retrieval plan builder (Phase 6A.5 Part 1B)."""

from __future__ import annotations

import hashlib
import re

from app.domain.hypothesis_retrieval.enums import (
    HypothesisRetrievalSourceType,
    RetrievalExecutionMode,
    RetrievalItemRelation,
    RetrievalQueryType,
)
from app.domain.hypothesis_retrieval.models import (
    PLAN_VERSION,
    HypothesisRetrievalContext,
    HypothesisRetrievalPlan,
    HypothesisRetrievalQuerySpec,
)
from app.domain.services.secret_masker import mask_secrets

_WS = re.compile(r"\s+")
_SECRET_LIKE = re.compile(
    r"(AKIA[0-9A-Z]{16})"
    r"|(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
    r"|(password\s*[=:])"
    r"|(secret\s*[=:])"
    r"|(api[_-]?key\s*[=:])",
    re.IGNORECASE,
)


def normalize_query_text(text: str) -> str:
    masked, _ = mask_secrets(text or "")
    return _WS.sub(" ", masked).strip().lower()


def is_secret_like_query(text: str) -> bool:
    if not text or not text.strip():
        return False
    if _SECRET_LIKE.search(text):
        return True
    _, count = mask_secrets(text)
    return count > 0


class HypothesisRetrievalPlanBuilder:
    """Generate bounded, deterministic query specs from retrieval context."""

    def __init__(
        self,
        *,
        max_queries: int = 6,
        max_query_chars: int = 2000,
        max_results_per_query: int = 10,
        historical_enabled: bool = True,
        static_kb_enabled: bool = True,
        artifact_enabled: bool = True,
        graph_context_enabled: bool = False,
        multi_query_enabled: bool = False,
        timeout_seconds: float = 45.0,
    ) -> None:
        self._max_queries = max(1, max_queries)
        self._max_query_chars = max(32, max_query_chars)
        self._top_k = max(1, max_results_per_query)
        self._historical_enabled = historical_enabled
        self._static_kb_enabled = static_kb_enabled
        self._artifact_enabled = artifact_enabled
        self._graph_context_enabled = graph_context_enabled
        self._multi_query_enabled = multi_query_enabled
        self._timeout = timeout_seconds

    def build(
        self,
        context: HypothesisRetrievalContext,
        *,
        session_id: str | None = None,
    ) -> HypothesisRetrievalPlan:
        warnings: list[str] = []
        specs: list[HypothesisRetrievalQuerySpec | None] = []

        knowledge_sources = self._knowledge_sources()
        artifact_sources = (
            [HypothesisRetrievalSourceType.ARTIFACT] if self._artifact_enabled else []
        )
        graph_sources = (
            [HypothesisRetrievalSourceType.GRAPH] if self._graph_context_enabled else []
        )
        temporal_sources = [HypothesisRetrievalSourceType.TEMPORAL]

        # 1. Causal claim (always if valid)
        specs.append(
            self._maybe_spec(
                query_id="q_causal_claim",
                query_type=RetrievalQueryType.CAUSAL_CLAIM,
                text=context.causal_claim,
                source_types=knowledge_sources + artifact_sources + temporal_sources,
                priority=10,
                reason="primary_causal_claim",
                originating_field="causal_claim",
                expected_relation=RetrievalItemRelation.SUPPORT_CANDIDATE,
                target_category=context.category_code,
                graph_node_ids=_seed_nodes(context),
            )
        )

        # 2. Error signature
        if context.error_signature:
            specs.append(
                self._maybe_spec(
                    query_id="q_error_signature",
                    query_type=RetrievalQueryType.ERROR_SIGNATURE,
                    text=str(context.error_signature),
                    source_types=knowledge_sources + temporal_sources,
                    priority=20,
                    reason="primary_failure_signature",
                    originating_field="error_signature",
                    expected_relation=RetrievalItemRelation.SUPPORT_CANDIDATE,
                )
            )

        # 3. Category
        if context.category_code:
            label_parts = [
                context.category_code,
                context.level_1_code,
                context.level_2_code,
                context.level_3_code,
                context.title,
            ]
            specs.append(
                self._maybe_spec(
                    query_id="q_failure_category",
                    query_type=RetrievalQueryType.FAILURE_CATEGORY,
                    text=" ".join(p for p in label_parts if p),
                    source_types=knowledge_sources,
                    priority=30,
                    reason="frozen_category_code",
                    originating_field="category_code",
                    target_category=context.category_code,
                    expected_relation=RetrievalItemRelation.CONTEXT,
                )
            )

        # 4. Artifact / path
        if context.affected_artifact_id or context.affected_path:
            specs.append(
                self._maybe_spec(
                    query_id="q_artifact_reference",
                    query_type=RetrievalQueryType.ARTIFACT_REFERENCE,
                    text=" ".join(
                        filter(
                            None,
                            [
                                context.affected_artifact_id,
                                context.affected_path,
                                context.title,
                            ],
                        )
                    ),
                    source_types=artifact_sources + knowledge_sources,
                    priority=40,
                    reason="affected_artifact",
                    originating_field="affected_artifact_id",
                    target_paths=[p for p in [context.affected_path] if p],
                    expected_relation=RetrievalItemRelation.CONTEXT,
                )
            )

        # 5. Root / observed labels via graph neighborhood
        root_label = _node_label(context, context.root_cause_node_id)
        observed_label = _node_label(context, context.observed_failure_node_id)
        if root_label or observed_label:
            specs.append(
                self._maybe_spec(
                    query_id="q_graph_neighborhood",
                    query_type=RetrievalQueryType.GRAPH_NEIGHBORHOOD,
                    text=" ".join(
                        filter(
                            None,
                            [root_label, observed_label, context.causal_claim[:120]],
                        )
                    ),
                    source_types=graph_sources + artifact_sources + temporal_sources,
                    priority=45,
                    reason="root_and_observed_node_labels",
                    originating_field="root_cause_node_id",
                    graph_node_ids=_seed_nodes(context),
                    expected_relation=RetrievalItemRelation.CONTEXT,
                )
            )

        # 6. Permission actions
        for idx, action in enumerate(context.permission_actions[:2], start=1):
            specs.append(
                self._maybe_spec(
                    query_id=f"q_permission_action_{idx}",
                    query_type=RetrievalQueryType.PERMISSION_ACTION,
                    text=action,
                    source_types=knowledge_sources + artifact_sources + graph_sources,
                    priority=50 + idx,
                    reason="permission_action",
                    originating_field="permission_actions",
                    target_actions=[action],
                    expected_relation=RetrievalItemRelation.SUPPORT_CANDIDATE,
                )
            )

        # 7. Resource identifiers
        for idx, resource in enumerate(context.resource_identifiers[:2], start=1):
            specs.append(
                self._maybe_spec(
                    query_id=f"q_resource_{idx}",
                    query_type=RetrievalQueryType.RESOURCE_REFERENCE,
                    text=resource,
                    source_types=artifact_sources + graph_sources + knowledge_sources,
                    priority=60 + idx,
                    reason="resource_identifier",
                    originating_field="resource_identifiers",
                    target_resource_identifiers=[resource],
                    expected_relation=RetrievalItemRelation.CONTEXT,
                )
            )

        # 8. Expected / falsifying observations
        if context.expected_observations:
            specs.append(
                self._maybe_spec(
                    query_id="q_expected_observation",
                    query_type=RetrievalQueryType.EXPECTED_OBSERVATION,
                    text=context.expected_observations[0],
                    source_types=artifact_sources + temporal_sources + knowledge_sources,
                    priority=70,
                    reason="expected_observation",
                    originating_field="expected_observations",
                    expected_relation=RetrievalItemRelation.SUPPORT_CANDIDATE,
                )
            )
        if context.falsifying_observations:
            specs.append(
                self._maybe_spec(
                    query_id="q_falsifying_observation",
                    query_type=RetrievalQueryType.FALSIFYING_OBSERVATION,
                    text=context.falsifying_observations[0],
                    source_types=artifact_sources + temporal_sources + knowledge_sources,
                    priority=75,
                    reason="falsifying_observation",
                    originating_field="falsifying_observations",
                    expected_relation=RetrievalItemRelation.CONTRADICTION_CANDIDATE,
                )
            )

        # 9. Historical similarity when enabled
        if self._historical_enabled and context.causal_claim:
            hist_sources = [HypothesisRetrievalSourceType.HISTORICAL_INCIDENT]
            specs.append(
                self._maybe_spec(
                    query_id="q_historical_similarity",
                    query_type=RetrievalQueryType.HISTORICAL_SIMILARITY,
                    text=" ".join(
                        filter(
                            None,
                            [
                                context.category_code,
                                context.error_signature,
                                context.causal_claim[:240],
                            ],
                        )
                    ),
                    source_types=hist_sources,
                    priority=90,
                    reason="historical_similarity_enabled",
                    originating_field="causal_claim",
                    expected_relation=RetrievalItemRelation.CONTEXT,
                    target_category=context.category_code,
                )
            )

        # Filter invalid / empty / oversized / secret-like; dedupe; bound.
        accepted: list[HypothesisRetrievalQuerySpec] = []
        seen_norm: set[str] = set()
        for spec in specs:
            if spec is None:
                continue
            if not spec.normalized_query:
                warnings.append(f"rejected_empty:{spec.query_id}")
                continue
            if len(spec.query_text) > self._max_query_chars:
                warnings.append(f"rejected_oversized:{spec.query_id}")
                continue
            if spec.metadata.get("secret_like") or is_secret_like_query(spec.query_text):
                warnings.append(f"rejected_secret_like:{spec.query_id}")
                continue
            if not spec.source_types:
                warnings.append(f"rejected_no_sources:{spec.query_id}")
                continue
            if spec.normalized_query in seen_norm:
                warnings.append(f"deduped:{spec.query_id}")
                continue
            seen_norm.add(spec.normalized_query)
            accepted.append(spec)

        accepted.sort(key=lambda s: (s.priority, s.query_id))
        if not self._multi_query_enabled and accepted:
            accepted = accepted[:1]
            warnings.append("multi_query_disabled_single_query_mode")
        elif len(accepted) > self._max_queries:
            warnings.append(f"bounded_queries:{len(accepted)}->{self._max_queries}")
            accepted = accepted[: self._max_queries]

        enabled = _sorted_source_types(
            [s for spec in accepted for s in spec.source_types]
        )
        excluded: list[HypothesisRetrievalSourceType] = [
            s
            for s in HypothesisRetrievalSourceType
            if s not in enabled
            and s
            not in {
                HypothesisRetrievalSourceType.DOCUMENTATION,
                HypothesisRetrievalSourceType.CLASSIFICATION,
                HypothesisRetrievalSourceType.REPOSITORY_CHANGE,
            }
        ]

        mode = (
            RetrievalExecutionMode.MULTI_QUERY
            if self._multi_query_enabled and len(accepted) > 1
            else RetrievalExecutionMode.SINGLE_QUERY
            if accepted
            else RetrievalExecutionMode.DISABLED
        )

        query_ids = ":".join(s.query_id for s in accepted)
        plan_key = hashlib.sha256(
            f"{context.hypothesis_id}:{PLAN_VERSION}:{query_ids}".encode()
        ).hexdigest()[:24]

        return HypothesisRetrievalPlan(
            hypothesis_id=context.hypothesis_id,
            session_id=session_id,
            execution_mode=mode,
            plan_version=PLAN_VERSION,
            query_specs=accepted,
            enabled_source_types=enabled,
            excluded_source_types=excluded,
            graph_constraints={
                "root_cause_node_id": context.root_cause_node_id,
                "observed_failure_node_id": context.observed_failure_node_id,
                "causal_path_node_ids": list(context.causal_path_node_ids),
            },
            artifact_constraints={
                "affected_artifact_id": context.affected_artifact_id,
                "affected_path": context.affected_path,
            },
            repository_constraints={
                "commit_sha": context.commit_sha,
                "workflow_path": context.workflow_path,
            },
            time_constraints={
                "temporal_primary_event_id": context.temporal_primary_event_id,
            },
            result_limits={
                "max_queries": self._max_queries,
                "top_k": self._top_k,
            },
            timeout_seconds=self._timeout,
            cache_policy={"enabled": True, "plan_version": PLAN_VERSION},
            warnings=warnings,
            plan_key=plan_key,
        )

    def _knowledge_sources(self) -> list[HypothesisRetrievalSourceType]:
        if not self._static_kb_enabled:
            return []
        return [
            HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
            HypothesisRetrievalSourceType.VECTOR_KNOWLEDGE,
            HypothesisRetrievalSourceType.LEXICAL_KNOWLEDGE,
        ]

    def _maybe_spec(
        self,
        *,
        query_id: str,
        query_type: RetrievalQueryType,
        text: str | None,
        source_types: list[HypothesisRetrievalSourceType],
        priority: int,
        reason: str,
        originating_field: str,
        expected_relation: RetrievalItemRelation = RetrievalItemRelation.UNKNOWN,
        target_category: str | None = None,
        target_paths: list[str] | None = None,
        target_actions: list[str] | None = None,
        target_resource_identifiers: list[str] | None = None,
        graph_node_ids: list[str] | None = None,
    ) -> HypothesisRetrievalQuerySpec | None:
        raw = (text or "").strip()
        if not raw:
            return None
        # Detect secrets on raw text before masking — masking would hide AKIA-style patterns.
        secret_like = is_secret_like_query(raw)
        masked, mask_count = mask_secrets(raw)
        if mask_count > 0:
            secret_like = True
        masked = masked.strip()[: self._max_query_chars]
        return HypothesisRetrievalQuerySpec(
            query_id=query_id,
            query_type=query_type,
            query_text=masked,
            normalized_query=normalize_query_text(masked),
            source_types=_sorted_source_types(source_types),
            target_category=target_category,
            target_paths=list(target_paths or []),
            target_actions=list(target_actions or []),
            target_resource_identifiers=list(target_resource_identifiers or []),
            graph_node_ids=list(graph_node_ids or []),
            expected_relation=expected_relation,
            top_k=self._top_k,
            priority=priority,
            reason=reason,
            originating_rule_id=f"plan_builder_{PLAN_VERSION}",
            originating_hypothesis_field=originating_field,
            metadata={"secret_like": secret_like} if secret_like else {},
        )


def _seed_nodes(context: HypothesisRetrievalContext) -> list[str]:
    return sorted(
        {
            n
            for n in [
                context.root_cause_node_id,
                context.observed_failure_node_id,
                *context.causal_path_node_ids,
            ]
            if n
        }
    )


def _node_label(context: HypothesisRetrievalContext, node_id: str | None) -> str | None:
    if not node_id:
        return None
    for node in context.graph_neighborhood_nodes:
        key = str(node.get("stable_key") or node.get("node_id") or "")
        if key == node_id:
            return str(node.get("label") or node_id)
    return node_id


def _sorted_source_types(
    sources: list[HypothesisRetrievalSourceType],
) -> list[HypothesisRetrievalSourceType]:
    unique = {s for s in sources if s is not None}
    return sorted(unique, key=lambda s: s.value)
