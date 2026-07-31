"""Threshold-based open-set failure detection (Phase 6A.3).

Transparent rule/threshold detector — not a novel statistical open-set method.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.classification.enums import OpenSetStatus
from app.domain.classification.models import (
    ClassificationCandidateDetail,
    OpenSetAssessment,
    StageClassifierResult,
)
from app.domain.classification.taxonomy_registry import FailureTaxonomyRegistry

OPEN_SET_RULE_VERSION = "open_set_rules_v1"


@dataclass(slots=True)
class OpenSetThresholds:
    confidence_threshold: float = 0.55
    margin_threshold: float = 0.08
    distance_threshold: float = 0.65
    min_evidence_coverage: float = 0.25
    min_rule_coverage: float = 0.15
    category_thresholds: dict[str, dict[str, float]] = field(default_factory=dict)

    def for_category(self, code: str | None) -> dict[str, float]:
        base = {
            "confidence": self.confidence_threshold,
            "margin": self.margin_threshold,
            "distance": self.distance_threshold,
            "evidence_coverage": self.min_evidence_coverage,
            "rule_coverage": self.min_rule_coverage,
        }
        if not code:
            return base
        overrides = self.category_thresholds.get(code.lower(), {})
        base.update({k: float(v) for k, v in overrides.items() if k in base})
        return base


class OpenSetFailureDetector:
    """Decide whether the failure sufficiently matches a known frozen category."""

    def __init__(
        self,
        *,
        registry: FailureTaxonomyRegistry,
        thresholds: OpenSetThresholds | None = None,
        enabled: bool = True,
    ) -> None:
        self._registry = registry
        self._thresholds = thresholds or OpenSetThresholds()
        self._enabled = enabled

    def assess(
        self,
        *,
        candidates: list[ClassificationCandidateDetail],
        rule_result: StageClassifierResult | None,
        learned_result: StageClassifierResult | None,
        llm_result: StageClassifierResult | None,
        evidence_coverage: float,
        disagreement_level: str | None = None,
        graph_coverage: float | None = None,
        temporal_confidence: float | None = None,
        parser_novel_signature: bool = False,
    ) -> OpenSetAssessment:
        if not self._enabled:
            return OpenSetAssessment(
                status=OpenSetStatus.UNCERTAIN,
                explanation="Open-set detection disabled.",
                threshold_version=OPEN_SET_RULE_VERSION,
                triggered_conditions=["disabled"],
            )

        top = candidates[0] if candidates else None
        second = candidates[1] if len(candidates) > 1 else None
        top_code = top.category_code if top else None
        max_known = float(top.score) if top else 0.0
        margin = (float(top.score) - float(second.score)) if top and second else max_known
        thr = self._thresholds.for_category(top_code)

        rule_cov = 0.0
        if rule_result and rule_result.executed and rule_result.matched_rules:
            deterministic = [
                r
                for r in rule_result.matched_rules
                if not r.startswith(("keyword:", "policy:", "fallback:"))
            ]
            rule_cov = min(1.0, 0.35 * len(deterministic)) if deterministic else 0.0

        representation_distance = None
        if learned_result and learned_result.representation_quality is not None:
            representation_distance = max(0.0, 1.0 - float(learned_result.representation_quality))

        evidence = float(evidence_coverage)
        if graph_coverage is not None:
            evidence = min(1.0, (evidence + float(graph_coverage)) / 2.0)

        triggered: list[str] = []
        unknown_votes = 0
        uncertain_votes = 0

        def _fire(rule_id: str, *, unknown: bool = False, uncertain: bool = False) -> None:
            nonlocal unknown_votes, uncertain_votes
            triggered.append(f"{OPEN_SET_RULE_VERSION}:{rule_id}")
            if unknown:
                unknown_votes += 1
            if uncertain:
                uncertain_votes += 1

        mapped_ok = top_code is not None and self._registry.is_valid_category(top_code)
        if not mapped_ok or top_code == "unknown_failure":
            _fire("invalid_or_unknown_category", unknown=True)

        if rule_cov < thr["rule_coverage"]:
            _fire("no_or_weak_rule_coverage", uncertain=True)
            if rule_cov <= 0.0:
                _fire("no_deterministic_rule_match", unknown=True)

        if max_known < thr["confidence"]:
            _fire("learned_or_fused_confidence_below_threshold", unknown=True)

        if margin < thr["margin"]:
            _fire("top_two_margin_below_threshold", uncertain=True)

        if representation_distance is not None and representation_distance > thr["distance"]:
            _fire("representation_distance_exceeds_threshold", unknown=True)

        if evidence < thr["evidence_coverage"]:
            _fire("evidence_coverage_below_threshold", uncertain=True)

        if llm_result and llm_result.executed and llm_result.category_code:
            if not self._registry.is_valid_category(llm_result.category_code):
                _fire("llm_category_unsupported", unknown=True)
            elif llm_result.evidence_ids == [] and llm_result.confidence > 0.5:
                _fire("llm_category_without_evidence", uncertain=True)

        if disagreement_level in {"LOW", "SEVERE"}:
            _fire("model_disagreement", uncertain=True)
            if disagreement_level == "SEVERE":
                _fire("severe_disagreement", unknown=True)

        if temporal_confidence is not None and temporal_confidence < 0.35:
            _fire("temporal_localisation_inconclusive", uncertain=True)

        if parser_novel_signature:
            _fire("novel_unsupported_tool_signature", unknown=True)

        # Security categories require stronger evidence before KNOWN.
        if (
            top_code in {"aws_permission_failure", "security_misconfiguration"}
            and evidence < max(thr["evidence_coverage"], 0.35)
            and rule_cov < 0.3
        ):
            _fire("security_requires_stronger_evidence", uncertain=True)

        unknown_score = min(1.0, 0.18 * unknown_votes + 0.08 * uncertain_votes)
        status = OpenSetStatus.KNOWN
        if unknown_votes >= 3 or (unknown_votes >= 2 and max_known < thr["confidence"]):
            status = OpenSetStatus.UNKNOWN
        elif unknown_votes >= 1 or uncertain_votes >= 2 or max_known < thr["confidence"] + 0.1:
            status = OpenSetStatus.UNCERTAIN
        elif (
            mapped_ok
            and top_code != "unknown_failure"
            and max_known >= thr["confidence"]
            and margin >= thr["margin"]
            and disagreement_level not in {"SEVERE"}
        ):
            status = OpenSetStatus.KNOWN
        else:
            status = OpenSetStatus.UNCERTAIN

        explanation = (
            f"Open-set status={status.value}; max_known={max_known:.3f}; "
            f"margin={margin:.3f}; rule_coverage={rule_cov:.3f}; "
            f"evidence_coverage={evidence:.3f}; triggered={len(triggered)}."
        )
        return OpenSetAssessment(
            status=status,
            unknown_score=round(unknown_score, 4),
            maximum_known_score=round(max_known, 4),
            top_two_margin=round(margin, 4),
            rule_coverage=round(rule_cov, 4),
            representation_distance=(
                round(representation_distance, 4) if representation_distance is not None else None
            ),
            evidence_coverage=round(evidence, 4),
            disagreement_level=disagreement_level,
            threshold_version=OPEN_SET_RULE_VERSION,
            triggered_conditions=triggered,
            explanation=explanation,
        )


def parse_category_thresholds_json(raw: str | dict[str, Any] | None) -> dict[str, dict[str, float]]:
    """Parse OPEN_SET_CATEGORY_THRESHOLDS_JSON; raise ValueError if malformed."""
    if raw is None or raw == "" or raw == {}:
        return {}
    data: Any = raw
    if isinstance(raw, str):
        import json

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed OPEN_SET_CATEGORY_THRESHOLDS_JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("OPEN_SET_CATEGORY_THRESHOLDS_JSON must be a JSON object")
    out: dict[str, dict[str, float]] = {}
    allowed = {"confidence", "margin", "distance", "evidence_coverage", "rule_coverage"}
    for cat, vals in data.items():
        if not isinstance(vals, dict):
            raise ValueError(f"Thresholds for '{cat}' must be an object")
        cleaned: dict[str, float] = {}
        for k, v in vals.items():
            if k not in allowed:
                raise ValueError(f"Unknown threshold key '{k}' for category '{cat}'")
            try:
                fv = float(v)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Threshold '{k}' for '{cat}' must be numeric") from exc
            if not 0.0 <= fv <= 1.0:
                raise ValueError(f"Threshold '{k}' for '{cat}' must be in [0,1]")
            cleaned[k] = fv
        out[str(cat).lower()] = cleaned
    return out
