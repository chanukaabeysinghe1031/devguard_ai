"""Structured classification disagreement analysis (Phase 6A.3).

Severe disagreement is never resolved by simple majority voting.
"""

from __future__ import annotations

from app.domain.classification.enums import (
    AgreementLevel,
    ClassificationConflictType,
    DisagreementRecommendedAction,
)
from app.domain.classification.models import (
    ClassificationDisagreementResult,
    StageClassifierResult,
)
from app.domain.classification.taxonomy_registry import FailureTaxonomyRegistry


class ClassificationDisagreementAnalyzer:
    def __init__(self, *, registry: FailureTaxonomyRegistry, enabled: bool = True) -> None:
        self._registry = registry
        self._enabled = enabled

    def analyze(
        self,
        *,
        rule_result: StageClassifierResult | None,
        learned_result: StageClassifierResult | None,
        llm_result: StageClassifierResult | None,
        graph_category_hint: str | None = None,
        temporal_category_hint: str | None = None,
        historical_category_hint: str | None = None,
    ) -> ClassificationDisagreementResult:
        if not self._enabled:
            return ClassificationDisagreementResult(
                agreement_level=AgreementLevel.NOT_APPLICABLE,
                explanation="Disagreement analysis disabled.",
            )

        votes: list[tuple[str, str]] = []
        for stage, result in (
            ("rule", rule_result),
            ("learned", learned_result),
            ("llm", llm_result),
        ):
            if (
                result
                and result.executed
                and result.category_code
                and self._registry.is_valid_category(result.category_code)
            ):
                votes.append((stage, result.category_code.lower()))

        signal_hints: list[tuple[str, str]] = []
        for stage, hint in (
            ("graph", graph_category_hint),
            ("temporal", temporal_category_hint),
            ("historical", historical_category_hint),
        ):
            if hint and self._registry.is_valid_category(hint):
                signal_hints.append((stage, hint.lower()))

        all_codes = [c for _, c in votes] + [c for _, c in signal_hints]
        if len(all_codes) < 2:
            return ClassificationDisagreementResult(
                agreement_level=AgreementLevel.NOT_APPLICABLE,
                agreed_level_3=all_codes[0] if all_codes else None,
                recommended_action=DisagreementRecommendedAction.REQUEST_MORE_EVIDENCE,
                additional_evidence_needed=["additional_classifier_or_artifact_signals"],
                explanation="Fewer than two comparable classification signals.",
                conflict_type=ClassificationConflictType.INSUFFICIENT_EVIDENCE,
            )

        unique = sorted(set(all_codes))
        paths = {c: self._registry.map_code(c) for c in unique}
        level1s = {p.level_1_code for p in paths.values()}
        level2s = {p.level_2_code for p in paths.values()}
        level3s = {p.level_3_code for p in paths.values()}

        classifier_codes = [c for _, c in votes]
        classifier_conflict = (
            len(set(classifier_codes)) > 1 if len(classifier_codes) >= 2 else False
        )
        evidence_conflict = False
        if graph_category_hint and votes:
            primary = votes[0][1]
            if graph_category_hint.lower() != primary:
                evidence_conflict = True

        conflict_type = ClassificationConflictType.NONE
        if "unknown_failure" in unique and len(unique) > 1:
            conflict_type = ClassificationConflictType.KNOWN_VS_UNKNOWN
        elif len(level1s) > 1:
            conflict_type = ClassificationConflictType.DIFFERENT_DOMAIN
        elif len(level2s) > 1:
            conflict_type = ClassificationConflictType.SAME_DOMAIN_DIFFERENT_SUBCATEGORY
        elif classifier_conflict:
            conflict_type = ClassificationConflictType.RULE_VS_MODEL
        elif evidence_conflict:
            conflict_type = ClassificationConflictType.LOG_VS_GRAPH
        elif (
            temporal_category_hint
            and learned_result
            and learned_result.category_code
            and temporal_category_hint.lower() != learned_result.category_code.lower()
        ):
            conflict_type = ClassificationConflictType.TEMPORAL_VS_SEMANTIC

        if len(unique) == 1:
            path = paths[unique[0]]
            return ClassificationDisagreementResult(
                agreement_level=AgreementLevel.HIGH,
                agreed_level_1=path.level_1_code,
                agreed_level_2=path.level_2_code,
                agreed_level_3=path.level_3_code,
                conflict_type=ClassificationConflictType.NONE,
                recommended_action=DisagreementRecommendedAction.ACCEPT,
                explanation="All comparable signals agree on the same frozen category.",
            )

        # Domain distance heuristic: different L1 = 1.0, same L1 different L2 = 0.5, else 0.25
        if len(level1s) > 1:
            distance = 1.0
            level = AgreementLevel.SEVERE
            action = DisagreementRecommendedAction.MARK_UNCERTAIN
            penalty = 0.25
        elif len(level2s) > 1:
            distance = 0.5
            level = AgreementLevel.LOW
            action = DisagreementRecommendedAction.LOWER_CONFIDENCE
            penalty = 0.15
        else:
            distance = 0.25
            level = AgreementLevel.MODERATE
            action = DisagreementRecommendedAction.LOWER_CONFIDENCE
            penalty = 0.08

        if conflict_type == ClassificationConflictType.KNOWN_VS_UNKNOWN:
            level = AgreementLevel.SEVERE
            action = DisagreementRecommendedAction.MARK_UNKNOWN
            penalty = max(penalty, 0.2)

        if evidence_conflict and classifier_conflict:
            level = AgreementLevel.SEVERE
            action = DisagreementRecommendedAction.MARK_UNCERTAIN
            penalty = max(penalty, 0.25)

        # Never majority-vote a severe conflict to a winner.
        agreed_l1 = next(iter(level1s)) if len(level1s) == 1 else None
        agreed_l2 = next(iter(level2s)) if len(level2s) == 1 else None
        agreed_l3 = None if level in {AgreementLevel.SEVERE, AgreementLevel.LOW} else (
            next(iter(level3s)) if len(level3s) == 1 else None
        )

        needed: list[str] = []
        if evidence_conflict:
            needed.append("reconcile_graph_vs_log_category_signals")
        if classifier_conflict:
            needed.append("additional_deterministic_evidence")
        if conflict_type == ClassificationConflictType.DIFFERENT_DOMAIN:
            needed.append("targeted_retrieval_for_domain_disambiguation")
            action = DisagreementRecommendedAction.TRIGGER_TARGETED_RETRIEVAL_LATER

        return ClassificationDisagreementResult(
            agreement_level=level,
            agreed_level_1=agreed_l1,
            agreed_level_2=agreed_l2,
            agreed_level_3=agreed_l3,
            conflicting_candidates=unique,
            conflict_type=conflict_type,
            evidence_conflict=evidence_conflict,
            classifier_conflict=classifier_conflict,
            category_distance=distance,
            recommended_action=action,
            additional_evidence_needed=needed,
            confidence_penalty=penalty,
            explanation=(
                f"Disagreement level={level.value}; conflict={conflict_type.value}; "
                f"candidates={unique}. Severe conflicts are not majority-voted."
            ),
        )
