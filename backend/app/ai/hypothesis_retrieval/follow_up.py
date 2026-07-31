"""Bounded follow-up retrieval planning (max one round by default)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.hypothesis_retrieval.query_sanitizer import RetrievalQuerySanitizer
from app.ai.hypothesis_retrieval.versions import HYPOTHESIS_FOLLOW_UP_VERSION
from app.domain.hypothesis_retrieval.enums import (
    HypothesisRetrievalSourceType,
    RetrievalItemRelation,
    RetrievalQueryType,
)
from app.domain.hypothesis_retrieval.models import (
    HypothesisRetrievalContext,
    HypothesisRetrievalQuerySpec,
    HypothesisRetrievedItem,
)


@dataclass(slots=True)
class FollowUpDecision:
    should_follow_up: bool
    trigger_reasons: list[str] = field(default_factory=list)
    follow_up_specs: list[HypothesisRetrievalQuerySpec] = field(default_factory=list)
    strategy: str | None = None
    round_number: int = 1
    version: str = HYPOTHESIS_FOLLOW_UP_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_follow_up": self.should_follow_up,
            "trigger_reasons": list(self.trigger_reasons),
            "follow_up_specs": [s.to_dict() for s in self.follow_up_specs],
            "strategy": self.strategy,
            "round_number": self.round_number,
            "version": self.version,
        }


class HypothesisRetrievalFollowUpPlanner:
    """Plan at most one follow-up round when retrieval is weak."""

    def __init__(
        self,
        *,
        min_results: int = 2,
        min_relevance: float = 0.35,
        max_rounds: int = 1,
        max_query_chars: int = 2000,
    ) -> None:
        self._min_results = max(1, min_results)
        self._min_relevance = min_relevance
        self._max_rounds = max(1, min(2, max_rounds))
        self._sanitizer = RetrievalQuerySanitizer(max_chars=max_query_chars)

    def plan(
        self,
        context: HypothesisRetrievalContext,
        *,
        accepted_items: list[HypothesisRetrievedItem],
        existing_specs: list[HypothesisRetrievalQuerySpec],
        required_source_types: list[HypothesisRetrievalSourceType] | None = None,
        current_round: int = 0,
        max_relevance: float | None = None,
        had_exact_identifier_match: bool = False,
    ) -> FollowUpDecision:
        if current_round >= self._max_rounds:
            return FollowUpDecision(
                should_follow_up=False,
                trigger_reasons=["max_rounds_reached"],
                round_number=current_round,
            )

        reasons: list[str] = []
        if len(accepted_items) < self._min_results:
            reasons.append("below_min_results")
        if max_relevance is not None and max_relevance < self._min_relevance:
            reasons.append("below_min_relevance")
        if not had_exact_identifier_match:
            reasons.append("no_exact_identifier_match")

        present_sources = {i.source_type for i in accepted_items}
        required = required_source_types or []
        missing_required = [s for s in required if s not in present_sources]
        if missing_required:
            reasons.append("missing_required_sources")

        if context.expected_observations and not any(
            (obs or "").lower() in (i.text_excerpt or "").lower()
            for obs in context.expected_observations[:2]
            for i in accepted_items
        ):
            reasons.append("expected_observation_absent")

        if (context.open_set_status or "").upper() in {"UNKNOWN", "OPEN", "NOVEL"}:
            reasons.append("open_set_needs_broader_signature")

        strong = (
            len(accepted_items) >= self._min_results
            and (max_relevance is None or max_relevance >= self._min_relevance)
            and had_exact_identifier_match
            and not missing_required
        )
        if strong or not reasons:
            return FollowUpDecision(
                should_follow_up=False,
                trigger_reasons=["strong_or_no_trigger"] if strong else [],
                round_number=current_round + 1,
            )

        strategy, specs = self._build_specs(context, existing_specs, reasons)
        return FollowUpDecision(
            should_follow_up=bool(specs),
            trigger_reasons=reasons,
            follow_up_specs=specs,
            strategy=strategy,
            round_number=current_round + 1,
        )

    def _build_specs(
        self,
        context: HypothesisRetrievalContext,
        existing: list[HypothesisRetrievalQuerySpec],
        reasons: list[str],
    ) -> tuple[str, list[HypothesisRetrievalQuerySpec]]:
        existing_norm = {s.normalized_query for s in existing}
        specs: list[HypothesisRetrievalQuerySpec] = []
        strategy = "simplify_exact_signature"

        if "open_set_needs_broader_signature" in reasons or "below_min_results" in reasons:
            strategy = "simplify_exact_signature"
            text = (context.error_signature or context.causal_claim or "")[:180]
            sanitized = self._sanitizer.sanitize(text)
            if sanitized.accepted and sanitized.normalized not in existing_norm:
                specs.append(
                    HypothesisRetrievalQuerySpec(
                        query_id="followup_exact_signature",
                        query_type=RetrievalQueryType.ERROR_SIGNATURE,
                        query_text=sanitized.text,
                        normalized_query=sanitized.normalized,
                        source_types=[
                            HypothesisRetrievalSourceType.LEXICAL_KNOWLEDGE,
                            HypothesisRetrievalSourceType.VECTOR_KNOWLEDGE,
                            HypothesisRetrievalSourceType.ARTIFACT,
                        ],
                        expected_relation=RetrievalItemRelation.SUPPORT_CANDIDATE,
                        priority=5,
                        reason="follow_up_simplify_signature",
                        metadata={
                            "follow_up_round": 1,
                            "strategy": strategy,
                            "version": HYPOTHESIS_FOLLOW_UP_VERSION,
                        },
                    )
                )

        if "missing_required_sources" in reasons or "no_exact_identifier_match" in reasons:
            strategy = "remove_optional_filters_add_history"
            text = f"{context.category_code or ''} {context.causal_claim[:160]}".strip()
            sanitized = self._sanitizer.sanitize(text)
            if sanitized.accepted and sanitized.normalized not in existing_norm:
                specs.append(
                    HypothesisRetrievalQuerySpec(
                        query_id="followup_historical",
                        query_type=RetrievalQueryType.HISTORICAL_SIMILARITY,
                        query_text=sanitized.text,
                        normalized_query=sanitized.normalized,
                        source_types=[HypothesisRetrievalSourceType.HISTORICAL_INCIDENT],
                        expected_relation=RetrievalItemRelation.CONTEXT,
                        priority=6,
                        reason="follow_up_historical",
                        metadata={
                            "follow_up_round": 1,
                            "strategy": strategy,
                            "removed_optional_filters": True,
                            "version": HYPOTHESIS_FOLLOW_UP_VERSION,
                        },
                    )
                )

        if "expected_observation_absent" in reasons and context.expected_observations:
            strategy = "target_expected_observation"
            obs = context.expected_observations[0]
            sanitized = self._sanitizer.sanitize(obs)
            if sanitized.accepted and sanitized.normalized not in existing_norm:
                specs.append(
                    HypothesisRetrievalQuerySpec(
                        query_id="followup_expected_obs",
                        query_type=RetrievalQueryType.EXPECTED_OBSERVATION,
                        query_text=sanitized.text,
                        normalized_query=sanitized.normalized,
                        source_types=[
                            HypothesisRetrievalSourceType.ARTIFACT,
                            HypothesisRetrievalSourceType.TEMPORAL,
                        ],
                        expected_relation=RetrievalItemRelation.SUPPORT_CANDIDATE,
                        priority=4,
                        reason="follow_up_expected_observation",
                        metadata={
                            "follow_up_round": 1,
                            "strategy": strategy,
                            "version": HYPOTHESIS_FOLLOW_UP_VERSION,
                        },
                    )
                )

        return strategy, specs[:2]
