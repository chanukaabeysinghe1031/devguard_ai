"""Hypothesis-specific source routing."""

from __future__ import annotations

from app.ai.hypothesis_retrieval.versions import HYPOTHESIS_SOURCE_ROUTER_VERSION
from app.domain.hypothesis_retrieval.enums import (
    HypothesisRetrievalSourceType,
    QueryIntentType,
)
from app.domain.hypothesis_retrieval.models import (
    HypothesisQueryIntent,
    HypothesisRetrievalContext,
    HypothesisRetrievalQuerySpec,
    HypothesisSourceRoutingDecision,
)

S = HypothesisRetrievalSourceType


class HypothesisRetrievalSourceRouter:
    """Route queries to suitable adapters based on category and intent."""

    def __init__(
        self,
        *,
        max_source_types: int = 5,
        artifact_enabled: bool = True,
        graph_enabled: bool = False,
        historical_enabled: bool = True,
        static_kb_enabled: bool = True,
    ) -> None:
        self._max = max(1, max_source_types)
        self._artifact = artifact_enabled
        self._graph = graph_enabled
        self._historical = historical_enabled
        self._static = static_kb_enabled

    def route(
        self,
        context: HypothesisRetrievalContext,
        spec: HypothesisRetrievalQuerySpec,
        intent: HypothesisQueryIntent | None = None,
    ) -> HypothesisSourceRoutingDecision:
        category = (context.category_code or "").upper()
        claim = (context.causal_claim or "").lower()
        intent_type = intent.intent_type if intent else None

        required, optional = self._profile(category, claim, intent_type)
        unavailable: list[HypothesisRetrievalSourceType] = []
        selected: list[HypothesisRetrievalSourceType] = []

        for src in required + optional:
            if src in selected:
                continue
            if not self._available(src):
                unavailable.append(src)
                continue
            selected.append(src)
            if len(selected) >= self._max:
                break

        # Preserve any already-present source types that remain available.
        for src in spec.source_types:
            if src not in selected and self._available(src) and len(selected) < self._max:
                selected.append(src)

        priorities = {s.value: idx for idx, s in enumerate(selected, start=1)}
        was_downgraded = bool(unavailable) and len(selected) < len(required)
        return HypothesisSourceRoutingDecision(
            query_id=spec.query_id,
            selected_sources=selected,
            required_sources=[s for s in required if self._available(s)],
            optional_sources=[s for s in optional if self._available(s)],
            excluded_sources=[],
            unavailable_sources=unavailable,
            source_priorities=priorities,
            reasons=[
                f"category={category or 'UNKNOWN'}",
                f"intent={intent_type.value if intent_type else 'none'}",
            ],
            routing_version=HYPOTHESIS_SOURCE_ROUTER_VERSION,
            was_downgraded=was_downgraded,
            downgrade_reason="required_sources_unavailable" if was_downgraded else None,
        )

    def _available(self, source: HypothesisRetrievalSourceType) -> bool:
        if source == S.ARTIFACT:
            return self._artifact
        if source == S.GRAPH:
            return self._graph
        if source == S.HISTORICAL_INCIDENT:
            return self._historical
        if source in {
            S.STATIC_KNOWLEDGE,
            S.VECTOR_KNOWLEDGE,
            S.LEXICAL_KNOWLEDGE,
            S.DOCUMENTATION,
        }:
            return self._static
        if source == S.TEMPORAL:
            return True
        if source == S.REPOSITORY_CHANGE:
            return True
        return source != S.CLASSIFICATION

    def _profile(
        self,
        category: str,
        claim: str,
        intent_type: QueryIntentType | None,
    ) -> tuple[list[HypothesisRetrievalSourceType], list[HypothesisRetrievalSourceType]]:
        if intent_type == QueryIntentType.FIND_HISTORICAL_ANALOGUE:
            return [S.HISTORICAL_INCIDENT], [S.STATIC_KNOWLEDGE]
        if intent_type == QueryIntentType.FIND_OFFICIAL_CONSTRAINT:
            return [S.DOCUMENTATION, S.STATIC_KNOWLEDGE], [S.VECTOR_KNOWLEDGE]
        if intent_type == QueryIntentType.FIND_RESOURCE_RELATIONSHIP:
            return [S.GRAPH, S.ARTIFACT], [S.TEMPORAL]

        if self._is_iam(category, claim):
            return (
                [S.ARTIFACT, S.GRAPH, S.STATIC_KNOWLEDGE, S.DOCUMENTATION],
                [S.VECTOR_KNOWLEDGE, S.LEXICAL_KNOWLEDGE, S.HISTORICAL_INCIDENT],
            )
        if "wrong role" in claim or "assumed role" in claim or "role arn" in claim:
            return (
                [S.ARTIFACT, S.GRAPH, S.REPOSITORY_CHANGE, S.TEMPORAL],
                [S.HISTORICAL_INCIDENT, S.DOCUMENTATION],
            )
        if "TERRAFORM" in category or "terraform" in claim:
            return (
                [S.ARTIFACT, S.GRAPH, S.TEMPORAL],
                [S.DOCUMENTATION, S.HISTORICAL_INCIDENT],
            )
        if "DEPEND" in category or "depend" in claim or "package" in claim:
            return (
                [S.ARTIFACT, S.TEMPORAL, S.STATIC_KNOWLEDGE],
                [S.VECTOR_KNOWLEDGE, S.HISTORICAL_INCIDENT],
            )
        # Unknown / default
        return (
            [S.LEXICAL_KNOWLEDGE, S.VECTOR_KNOWLEDGE, S.ARTIFACT],
            [S.HISTORICAL_INCIDENT, S.DOCUMENTATION],
        )

    @staticmethod
    def _is_iam(category: str, claim: str) -> bool:
        if "IAM" in category or "PERMISSION" in category:
            return True
        return any(
            t in claim
            for t in ("iam", "permission", "accessdenied", "access denied", "s3:putobject")
        )
