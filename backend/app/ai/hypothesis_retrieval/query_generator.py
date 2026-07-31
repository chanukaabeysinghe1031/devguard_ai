"""Hypothesis-specific query generation from intents and identifiers."""

from __future__ import annotations

from app.ai.hypothesis_retrieval.identifiers import ExtractedIdentifiers
from app.ai.hypothesis_retrieval.query_sanitizer import RetrievalQuerySanitizer
from app.ai.hypothesis_retrieval.versions import HYPOTHESIS_QUERY_GENERATOR_VERSION
from app.domain.hypothesis_retrieval.enums import (
    HypothesisRetrievalSourceType,
    QueryIntentType,
    RetrievalItemRelation,
    RetrievalQueryType,
)
from app.domain.hypothesis_retrieval.models import (
    HypothesisQueryIntent,
    HypothesisRetrievalContext,
    HypothesisRetrievalQuerySpec,
)

_INTENT_TO_QUERY_TYPE: dict[QueryIntentType, RetrievalQueryType] = {
    QueryIntentType.CONFIRM_CAUSAL_CLAIM: RetrievalQueryType.CAUSAL_CLAIM,
    QueryIntentType.FIND_CONTRADICTION_CANDIDATE: RetrievalQueryType.FALSIFYING_OBSERVATION,
    QueryIntentType.RESOLVE_MISSING_EVIDENCE: RetrievalQueryType.CUSTOM_RULE,
    QueryIntentType.VERIFY_ARTIFACT_RELATIONSHIP: RetrievalQueryType.ARTIFACT_REFERENCE,
    QueryIntentType.FIND_HISTORICAL_ANALOGUE: RetrievalQueryType.HISTORICAL_SIMILARITY,
    QueryIntentType.FIND_OFFICIAL_CONSTRAINT: RetrievalQueryType.CUSTOM_RULE,
    QueryIntentType.FIND_POLICY_BEHAVIOR: RetrievalQueryType.PERMISSION_ACTION,
    QueryIntentType.FIND_CONFIGURATION_REQUIREMENT: RetrievalQueryType.FAILURE_CATEGORY,
    QueryIntentType.FIND_PRIOR_SUCCESS_DIFFERENCE: RetrievalQueryType.CUSTOM_RULE,
    QueryIntentType.FIND_EXACT_FAILURE_SIGNATURE: RetrievalQueryType.ERROR_SIGNATURE,
    QueryIntentType.FIND_RESOURCE_RELATIONSHIP: RetrievalQueryType.RESOURCE_REFERENCE,
    QueryIntentType.FIND_PERMISSION_RELATIONSHIP: RetrievalQueryType.PERMISSION_ACTION,
    QueryIntentType.EXPLORE_NOVEL_SIGNATURE: RetrievalQueryType.ERROR_SIGNATURE,
}


class HypothesisSpecificQueryGenerator:
    """Generate bounded, deterministic query specs from intents."""

    def __init__(
        self,
        *,
        sanitizer: RetrievalQuerySanitizer | None = None,
        max_expansions: int = 4,
        max_identifiers: int = 8,
        top_k: int = 10,
    ) -> None:
        self._sanitizer = sanitizer or RetrievalQuerySanitizer()
        self._max_expansions = max(1, max_expansions)
        self._max_identifiers = max(1, max_identifiers)
        self._top_k = max(1, top_k)

    def generate(
        self,
        context: HypothesisRetrievalContext,
        intents: list[HypothesisQueryIntent],
        identifiers: ExtractedIdentifiers,
        *,
        expansion_enabled: bool = False,
    ) -> list[HypothesisRetrievalQuerySpec]:
        specs: list[HypothesisRetrievalQuerySpec] = []
        id_slice = identifiers.all_identifiers[: self._max_identifiers]
        for intent in intents:
            families = self._families_for_intent(context, intent, id_slice)
            families = families[:1] if not expansion_enabled else families[:self._max_expansions]
            for fam_idx, (text, relation) in enumerate(families):
                sanitized = self._sanitizer.sanitize(text)
                if not sanitized.accepted:
                    continue
                query_type = _INTENT_TO_QUERY_TYPE.get(
                    intent.intent_type, RetrievalQueryType.CUSTOM_RULE
                )
                sources = list(intent.preferred_source_types) or [
                    HypothesisRetrievalSourceType.STATIC_KNOWLEDGE
                ]
                specs.append(
                    HypothesisRetrievalQuerySpec(
                        query_id=f"{intent.intent_id}:q{fam_idx}",
                        query_type=query_type,
                        query_text=sanitized.text,
                        normalized_query=sanitized.normalized,
                        source_types=sources,
                        target_category=context.category_code,
                        target_artifact_types=[],
                        target_paths=list(intent.target_source_paths),
                        target_resource_identifiers=list(intent.target_identifiers)
                        or list(id_slice[:4]),
                        target_actions=list(identifiers.aws_actions[:4]),
                        graph_node_ids=list(intent.target_entity_ids),
                        expected_relation=relation,
                        top_k=self._top_k,
                        priority=intent.priority + fam_idx,
                        reason=intent.reason,
                        originating_rule_id=intent.generating_rule_id,
                        originating_hypothesis_field=intent.intent_type.value,
                        metadata={
                            "intent_id": intent.intent_id,
                            "intent_type": intent.intent_type.value,
                            "identifiers_used": list(id_slice[: self._max_identifiers]),
                            "generator_version": HYPOTHESIS_QUERY_GENERATOR_VERSION,
                            "family_index": fam_idx,
                        },
                    )
                )
        specs.sort(key=lambda s: (s.priority, s.query_id))
        return specs

    def _families_for_intent(
        self,
        context: HypothesisRetrievalContext,
        intent: HypothesisQueryIntent,
        identifiers: list[str],
    ) -> list[tuple[str, RetrievalItemRelation]]:
        claim = (context.causal_claim or "").strip()
        signature = (context.error_signature or "").strip()
        id_text = " ".join(identifiers[:6])
        families: list[tuple[str, RetrievalItemRelation]] = []

        if intent.intent_type == QueryIntentType.CONFIRM_CAUSAL_CLAIM:
            families.append((claim or intent.objective, RetrievalItemRelation.SUPPORT_CANDIDATE))
            if signature:
                families.append(
                    (f"{signature} {claim[:120]}", RetrievalItemRelation.SUPPORT_CANDIDATE)
                )
            if id_text:
                families.append((id_text, RetrievalItemRelation.SUPPORT_CANDIDATE))
        elif intent.intent_type == QueryIntentType.FIND_EXACT_FAILURE_SIGNATURE:
            families.append(
                (signature or claim[:200], RetrievalItemRelation.SUPPORT_CANDIDATE)
            )
            if id_text:
                families.append(
                    (f"{signature} {id_text}".strip(), RetrievalItemRelation.SUPPORT_CANDIDATE)
                )
        elif intent.intent_type == QueryIntentType.FIND_CONTRADICTION_CANDIDATE:
            text = intent.falsifying_observation or intent.objective
            families.append((text, RetrievalItemRelation.CONTRADICTION_CANDIDATE))
        elif intent.intent_type == QueryIntentType.FIND_POLICY_BEHAVIOR:
            families.append(
                (
                    f"IAM evaluation explicit deny permissions boundary {id_text}".strip(),
                    RetrievalItemRelation.CONTEXT,
                )
            )
        elif intent.intent_type == QueryIntentType.VERIFY_ARTIFACT_RELATIONSHIP:
            path = context.affected_path or ""
            art = context.affected_artifact_id or ""
            families.append(
                (
                    f"artifact relationship {art} {path} {claim[:120]}".strip(),
                    RetrievalItemRelation.CONTEXT,
                )
            )
        elif intent.intent_type == QueryIntentType.FIND_PRIOR_SUCCESS_DIFFERENCE:
            families.append(
                (
                    f"previous successful run difference {context.commit_sha or ''} "
                    f"{' '.join(context.changed_files[:4])}".strip(),
                    RetrievalItemRelation.CONTEXT,
                )
            )
        elif intent.intent_type == QueryIntentType.FIND_HISTORICAL_ANALOGUE:
            families.append(
                (
                    f"{context.category_code or ''} {signature} {claim[:160]}".strip(),
                    RetrievalItemRelation.CONTEXT,
                )
            )
        elif intent.intent_type == QueryIntentType.FIND_OFFICIAL_CONSTRAINT:
            families.append(
                (
                    f"official documentation constraint {context.category_code or ''} "
                    f"{id_text}".strip(),
                    RetrievalItemRelation.CONTEXT,
                )
            )
        elif intent.intent_type == QueryIntentType.FIND_PERMISSION_RELATIONSHIP:
            actions = " ".join(identifiers[:4] or context.permission_actions[:4])
            families.append(
                (
                    f"permission relationship {actions} {claim[:120]}".strip(),
                    RetrievalItemRelation.SUPPORT_CANDIDATE,
                )
            )
        elif intent.intent_type == QueryIntentType.FIND_RESOURCE_RELATIONSHIP:
            families.append(
                (
                    f"resource relationship {' '.join(intent.target_entity_ids[:4])} "
                    f"{id_text}".strip(),
                    RetrievalItemRelation.CONTEXT,
                )
            )
        elif intent.intent_type == QueryIntentType.RESOLVE_MISSING_EVIDENCE:
            families.append(
                (
                    intent.evidence_gap or intent.objective,
                    RetrievalItemRelation.CONTEXT,
                )
            )
        elif intent.intent_type == QueryIntentType.EXPLORE_NOVEL_SIGNATURE:
            families.append(
                (
                    f"{signature or claim[:160]} {id_text}".strip(),
                    RetrievalItemRelation.UNKNOWN,
                )
            )
        else:
            families.append((intent.objective, RetrievalItemRelation.CONTEXT))

        if intent.expected_observation:
            families.append(
                (intent.expected_observation, RetrievalItemRelation.SUPPORT_CANDIDATE)
            )
        return [(t, r) for t, r in families if t and str(t).strip()]
