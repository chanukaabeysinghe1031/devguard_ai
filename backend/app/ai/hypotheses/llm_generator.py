"""Structured LLM causal hypothesis generator (Phase 6A.4).

Does not invent IDs. Strict schema validation. No verifier execution.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.domain.classification.taxonomy_registry import get_taxonomy_registry
from app.domain.hypotheses.enums import (
    HypothesisEvidenceRelation,
    HypothesisGeneratorType,
    HypothesisStatus,
)
from app.domain.hypotheses.models import (
    CausalHypothesis,
    HypothesisEvidenceLink,
    HypothesisGenerationContext,
)

HYPOTHESIS_PROMPT_VERSION = "hypothesis_v1"
MAX_LLM_HYPOTHESES = 5


def build_hypothesis_prompt(context: HypothesisGenerationContext) -> str:
    frozen = sorted(get_taxonomy_registry().to_dict()["frozen_codes"])
    payload = {
        "analysis_id": context.analysis_id,
        "open_set_status": context.open_set_status,
        "hierarchical_classification": context.hierarchical_classification,
        "top_candidates": context.top_classification_candidates[:5],
        "temporal_primary_failure": context.temporal_primary_failure,
        "graph_nodes": [
            {
                "id": n.get("stable_key") or n.get("id"),
                "type": n.get("node_type"),
                "label": n.get("label"),
                "source_path": n.get("source_path"),
            }
            for n in context.relevant_graph_nodes[:40]
        ],
        "graph_edges": [
            {
                "id": e.get("id") or e.get("stable_key"),
                "source": e.get("source_node_id") or e.get("source"),
                "target": e.get("target_node_id") or e.get("target"),
                "type": e.get("edge_type"),
            }
            for e in context.relevant_graph_edges[:60]
        ],
        "evidence": [
            {
                "id": ev.get("id"),
                "type": ev.get("evidence_type"),
                "excerpt": str(ev.get("excerpt") or "")[:240],
            }
            for ev in context.evidence_candidates[:20]
        ],
        "missing_artifacts": context.missing_artifacts[:12],
        "allowed_category_codes": frozen,
        "instructions": [
            "Generate competing causal hypotheses, not a single verified answer.",
            "Use only supplied node/edge/evidence/artifact IDs.",
            "Do not invent files, nodes, policies, resources, or evidence.",
            "Distinguish root causes from downstream symptoms.",
            "Return fewer hypotheses when evidence is limited; empty list if none supportable.",
            "Return JSON only matching the schema.",
        ],
    }
    return (
        f"PROMPT_VERSION={HYPOTHESIS_PROMPT_VERSION}\n"
        "Return JSON: {\"hypotheses\":[...]}.\n"
        + json.dumps(payload, ensure_ascii=True)
    )


def parse_llm_hypotheses(
    raw: str | dict[str, Any],
    *,
    context: HypothesisGenerationContext,
    max_hypotheses: int = MAX_LLM_HYPOTHESES,
) -> tuple[list[CausalHypothesis], list[str]]:
    """Parse and lightly shape LLM output. Reference validation happens separately."""
    errors: list[str] = []
    data: Any = raw
    if isinstance(raw, str):
        text = raw.strip()
        # Strip markdown fences if present.
        fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
        if fence:
            text = fence.group(1)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return [], [f"malformed_json:{exc}"]
    if not isinstance(data, dict):
        return [], ["root_not_object"]
    items = data.get("hypotheses")
    if items is None:
        return [], ["missing_hypotheses_key"]
    if not isinstance(items, list):
        return [], ["hypotheses_not_list"]
    if len(items) > max_hypotheses:
        errors.append(f"truncated_hypotheses:{len(items)}->{max_hypotheses}")
        items = items[:max_hypotheses]

    registry = get_taxonomy_registry()
    out: list[CausalHypothesis] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"item_{idx}_not_object")
            continue
        category = str(item.get("category_code") or "").strip().lower()
        if category and not registry.is_valid_category(category):
            errors.append(f"fabricated_category:{category}")
            continue
        path = registry.map_code(category) if category else registry.unknown_path()
        claim = str(item.get("causal_claim") or "").strip()
        title = str(item.get("title") or f"Hypothesis {idx}").strip()
        if not claim:
            errors.append(f"item_{idx}_empty_claim")
            continue
        links: list[HypothesisEvidenceLink] = []
        for rel_name, relation in (
            ("supporting_evidence", HypothesisEvidenceRelation.SUPPORTS),
            ("contradicting_evidence", HypothesisEvidenceRelation.CONTRADICTS),
        ):
            for ev in item.get(rel_name) or []:
                if not isinstance(ev, dict):
                    continue
                links.append(
                    HypothesisEvidenceLink(
                        evidence_type="llm_cited",
                        relation=relation,
                        explanation=str(ev.get("reason") or "")[:500],
                        confidence=0.5,
                        evidence_item_id=(
                            str(ev["evidence_id"]) if ev.get("evidence_id") else None
                        ),
                        graph_node_id=(
                            str(ev["graph_node_id"]) if ev.get("graph_node_id") else None
                        ),
                        graph_edge_id=(
                            str(ev["graph_edge_id"]) if ev.get("graph_edge_id") else None
                        ),
                        extraction_method="llm",
                    )
                )
        missing = [str(x) for x in (item.get("missing_evidence") or []) if x][:12]
        hyp = CausalHypothesis(
            hypothesis_key=str(item.get("hypothesis_key") or f"L{idx}"),
            title=title[:255],
            causal_claim=claim[:4000],
            category_code=category or None,
            level_1_code=path.level_1_code if category else None,
            level_2_code=path.level_2_code if category else None,
            level_3_code=path.level_3_code if category else None,
            root_cause_node_id=_opt_str(item.get("root_cause_node_id")),
            observed_failure_node_id=_opt_str(item.get("observed_failure_node_id")),
            causal_path_node_ids=[
                str(x) for x in (item.get("causal_path_node_ids") or []) if x
            ][:20],
            causal_path_edge_ids=[
                str(x) for x in (item.get("causal_path_edge_ids") or []) if x
            ][:30],
            evidence_links=links,
            expected_observations=[
                str(x) for x in (item.get("expected_observations") or []) if x
            ][:10],
            falsifying_observations=[
                str(x) for x in (item.get("falsifying_observations") or []) if x
            ][:10],
            proposed_verification_steps=[
                str(x) for x in (item.get("proposed_verification_steps") or []) if x
            ][:10],
            limitations=[str(x) for x in (item.get("limitations") or []) if x][:10],
            missing_evidence=missing,
            generator_type=HypothesisGeneratorType.LLM,
            generator_name="llm_causal_hypothesis",
            generator_version="v1",
            prompt_version=HYPOTHESIS_PROMPT_VERSION,
            generation_confidence=_clamp_conf(item.get("generation_confidence")),
            status=HypothesisStatus.GENERATED,
            rank_placeholder=idx,
        )
        out.append(hyp)
    return out, errors


def _opt_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _clamp_conf(value: Any) -> float:
    try:
        return round(max(0.0, min(1.0, float(value))), 4)
    except (TypeError, ValueError):
        return 0.4


class LLMCausalHypothesisGenerator:
    """Optional LLM stage. Without a callable provider, returns empty + skip reason."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        complete_json: Any | None = None,
        max_hypotheses: int = MAX_LLM_HYPOTHESES,
    ) -> None:
        self._enabled = enabled
        self._complete_json = complete_json
        self._max = max_hypotheses

    def generate(
        self, context: HypothesisGenerationContext
    ) -> tuple[list[CausalHypothesis], list[str], dict[str, Any]]:
        if not self._enabled:
            return [], ["llm_hypothesis_disabled"], {}
        if self._complete_json is None:
            return [], ["llm_provider_unavailable"], {}
        prompt = build_hypothesis_prompt(context)
        try:
            raw = self._complete_json(prompt)
        except Exception as exc:  # noqa: BLE001
            return [], [f"llm_call_failed:{type(exc).__name__}"], {}
        hyps, errors = parse_llm_hypotheses(raw, context=context, max_hypotheses=self._max)
        usage = {}
        if isinstance(raw, dict) and isinstance(raw.get("_usage"), dict):
            usage = dict(raw["_usage"])
        return hyps, errors, usage
