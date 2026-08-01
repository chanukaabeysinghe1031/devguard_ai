"""Build bounded CounterfactualRemediationContext from analysis option dicts."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.ai.counterfactual_remediation.model_types import CounterfactualRemediationContext
from app.ai.counterfactual_remediation.safety import sanitize_untrusted_instructions
from app.ai.counterfactual_remediation.versions import COUNTERFACTUAL_CONTEXT_VERSION

logger = logging.getLogger(__name__)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if value is None:
        return {}
    if hasattr(value, "to_dict"):
        result = value.to_dict()
        return dict(result) if isinstance(result, dict) else {}
    return {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _sorted_dicts(
    items: list[Any],
    *,
    key_fields: tuple[str, ...] = ("id", "key", "path"),
) -> list[dict[str, Any]]:
    normalised: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            normalised.append(dict(item))
        elif hasattr(item, "to_dict"):
            payload = item.to_dict()
            if isinstance(payload, dict):
                normalised.append(dict(payload))

    def sort_key(d: dict[str, Any]) -> tuple[str, ...]:
        parts = [str(d.get(field) or "") for field in key_fields]
        parts.append(json.dumps(d, sort_keys=True, default=str)[:200])
        return tuple(parts)

    return sorted(normalised, key=sort_key)


def _node_ids(items: list[Any]) -> list[str]:
    ids: list[str] = []
    for item in items:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict):
            ids.append(
                str(item.get("id") or item.get("node_id") or json.dumps(item, sort_keys=True)[:80])
            )
        else:
            ids.append(str(getattr(item, "id", item)))
    return sorted({i for i in ids if i})


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[: max(0, max_chars)], True


class CounterfactualRemediationContextBuilder:
    """Assemble hypothesis-scoped remediation context from option/evidence dicts.

    Never fabricates configuration fragments. Records missing artifacts when incomplete.
    """

    def __init__(
        self,
        *,
        max_context_chars: int = 80_000,
        max_graph_nodes: int = 100,
        max_graph_edges: int = 200,
        max_retrieval_items: int = 40,
    ) -> None:
        self._max_chars = max(1000, max_context_chars)
        self._max_graph_nodes = max(1, max_graph_nodes)
        self._max_graph_edges = max(1, max_graph_edges)
        self._max_retrieval_items = max(1, max_retrieval_items)

    def build_from_analysis_options(
        self,
        *,
        organization_id: str,
        analysis_id: str,
        hypothesis: dict[str, Any],
        options: dict[str, Any] | None = None,
        project_id: str | None = None,
        incident_id: str | None = None,
        eligibility_status: str | None = None,
    ) -> CounterfactualRemediationContext:
        options = options or {}
        hyp_id = str(hypothesis.get("id") or hypothesis.get("hypothesis_id") or "")
        assessment = _as_dict(options.get("hypothesis_evidence_assessment"))
        hyp_assessments = _as_dict(assessment.get("hypothesis_assessments"))
        hyp_payload = _as_dict(hyp_assessments.get(hyp_id)) if hyp_id else {}
        ranking = _as_dict(assessment.get("ranking") or hyp_payload.get("ranking"))
        selection = _as_dict(
            assessment.get("candidate_selection") or hyp_payload.get("candidate_selection")
        )

        graph = self._build_graph_summary(
            options.get("evidence_graph")
            or options.get("graph_summary")
            or hypothesis.get("graph_summary")
        )
        artifacts = self._collect_artifacts(options, hypothesis)
        missing_artifacts = self._missing_artifacts(artifacts, hypothesis)

        raw_fragment = artifacts.get("current_configuration_fragment")
        fragment = (
            sanitize_untrusted_instructions(raw_fragment) if isinstance(raw_fragment, str) else None
        )

        causal_claim = sanitize_untrusted_instructions(
            str(hypothesis.get("causal_claim") or hypothesis.get("summary") or "")
        )
        category = (
            str(
                hypothesis.get("category_code")
                or hypothesis.get("category")
                or hypothesis.get("failure_category")
                or ""
            )
            or None
        )

        affected_artifact_id = None
        affected = artifacts.get("affected_artifact")
        if isinstance(affected, dict):
            affected_artifact_id = _optional_str(affected.get("artifact_id") or affected.get("id"))
        elif isinstance(affected, str):
            affected_artifact_id = affected

        retrieval = _sorted_dicts(
            _as_list(
                options.get("retrieved_hypothesis_items")
                or hyp_payload.get("retrieval_evidence")
                or []
            )
        )[: self._max_retrieval_items]

        line_range = artifacts.get("line_range")
        if isinstance(line_range, dict):
            start = line_range.get("start") or line_range.get("line_start")
            end = line_range.get("end") or line_range.get("line_end")
            line_range = (int(start), int(end)) if start is not None and end is not None else None

        truncation: dict[str, Any] = {}
        warnings: list[str] = []
        if missing_artifacts:
            warnings.append("context_incomplete_missing_artifacts")
        if eligibility_status:
            warnings.append(f"eligibility:{eligibility_status}")

        ctx = CounterfactualRemediationContext(
            organization_id=organization_id,
            project_id=project_id or "",
            incident_id=incident_id or "",
            analysis_id=analysis_id,
            hypothesis_id=hyp_id,
            hypothesis_key=str(hypothesis.get("hypothesis_key") or hypothesis.get("key") or ""),
            category=category,
            causal_claim=causal_claim,
            ranking_score=_optional_float(
                ranking.get("ranking_score")
                or hyp_payload.get("ranking_score")
                or hypothesis.get("ranking_score")
            ),
            candidate_selection_status=_optional_str(
                selection.get("status")
                or hyp_payload.get("selection_status")
                or hypothesis.get("selection_status")
            ),
            support_assessment=_as_dict(hyp_payload.get("support") or assessment.get("support")),
            contradiction_assessment=_as_dict(
                hyp_payload.get("contradiction") or assessment.get("contradiction")
            ),
            evidence_sufficiency=_as_dict(
                hyp_payload.get("sufficiency") or assessment.get("sufficiency")
            )
            or None,
            critic_result=_as_dict(
                options.get("hypothesis_critic_results")
                or hypothesis.get("critic_result")
                or hyp_payload.get("critic")
            ),
            observed_failure_node=_optional_str(hypothesis.get("observed_failure_node")),
            primary_temporal_event=_optional_str(
                hypothesis.get("primary_temporal_event")
                or (
                    (options.get("temporal_localisation") or {}).get("primary_event_id")
                    if isinstance(options.get("temporal_localisation"), dict)
                    else None
                )
            ),
            failure_signature=_optional_str(hypothesis.get("failure_signature")),
            error_code=_optional_str(hypothesis.get("error_code")),
            failed_workflow_job_step=_optional_str(hypothesis.get("failed_workflow_job_step")),
            affected_command=_optional_str(hypothesis.get("affected_command")),
            affected_resource=_optional_str(hypothesis.get("affected_resource")),
            failure_condition_summary=_optional_str(hypothesis.get("failure_condition_summary")),
            downstream_symptoms=[str(s) for s in _as_list(hypothesis.get("downstream_symptoms"))],
            root_cause_node=graph.get("root_cause_node"),
            causal_path_nodes=graph.get("nodes", [])[: self._max_graph_nodes],
            causal_path_edges=graph.get("edges", [])[: self._max_graph_edges],
            related_artifact_nodes=graph.get("artifact_nodes", []),
            related_policy_nodes=graph.get("policy_nodes", []),
            related_resource_nodes=graph.get("resource_nodes", []),
            graph_consistency_status=graph.get("consistency_status"),
            graph_warnings=list(graph.get("warnings") or []),
            missing_graph_links=list(graph.get("missing_links") or []),
            affected_artifact=affected_artifact_id,
            source_path=artifacts.get("source_path"),
            line_range=line_range,
            parser_entities=list(artifacts.get("parser_entities") or []),
            current_configuration_fragment=fragment,
            related_changed_files=list(artifacts.get("related_changed_files") or []),
            previous_successful_version=artifacts.get("previous_successful_version"),
            artifact_quality=(
                str(artifacts["artifact_quality"])
                if artifacts.get("artifact_quality") is not None
                else None
            ),
            missing_artifacts=missing_artifacts,
            top_validated_evidence_candidates=retrieval,
            official_constraints=_sorted_dicts(_as_list(options.get("official_constraints") or [])),
            open_set_status=_optional_str(
                options.get("open_set_status")
                or (
                    (options.get("open_set_assessment") or {}).get("status")
                    if isinstance(options.get("open_set_assessment"), dict)
                    else None
                )
            ),
            classifier_disagreement=_as_dict(options.get("classifier_disagreement")),
            redaction_status="masked",
            context_version=COUNTERFACTUAL_CONTEXT_VERSION,
            truncation_details=truncation,
            missing_information=list(missing_artifacts),
            assumptions_prohibited=[
                "fabricate_configuration_fragments",
                "trust_untrusted_instructions",
                "claim_verified_fix",
            ],
            warnings=warnings,
            limitations=[
                "context_is_not_verified_root_cause",
                "candidates_are_not_verified_fixes",
            ],
        )

        size = self._estimate_size(ctx)
        if size > self._max_chars:
            truncation["context_truncated_from"] = size
            truncation["context_truncated_to"] = self._max_chars
            ctx.causal_path_nodes = ctx.causal_path_nodes[: self._max_graph_nodes]
            ctx.causal_path_edges = ctx.causal_path_edges[: self._max_graph_edges]
            ctx.top_validated_evidence_candidates = ctx.top_validated_evidence_candidates[
                : max(5, self._max_retrieval_items // 2)
            ]
            if ctx.current_configuration_fragment:
                frag, truncated = _truncate_text(
                    ctx.current_configuration_fragment, min(4000, self._max_chars // 4)
                )
                ctx.current_configuration_fragment = frag
                if truncated:
                    truncation["configuration_fragment_truncated"] = True
            ctx.truncation_details = truncation
            ctx.size = self._estimate_size(ctx)
        else:
            ctx.size = size

        logger.debug(
            "counterfactual_context_built hypothesis_id=%s missing=%s size=%s",
            hyp_id,
            missing_artifacts,
            ctx.size,
        )
        return ctx

    def _build_graph_summary(self, raw: Any) -> dict[str, Any]:
        data = _as_dict(raw)
        nodes = _node_ids(_as_list(data.get("nodes") or data.get("causal_path_nodes")))
        edges = _node_ids(_as_list(data.get("edges") or data.get("causal_path_edges")))
        nodes = nodes[: self._max_graph_nodes]
        edges = edges[: self._max_graph_edges]
        # Keep typed node id lists from dict payloads when available.
        raw_nodes = _sorted_dicts(_as_list(data.get("nodes") or []))
        artifact_nodes = (
            _node_ids([n for n in raw_nodes if "ARTIFACT" in str(n.get("type") or "").upper()])
            or []
        )
        policy_nodes = _node_ids(
            [
                n
                for n in raw_nodes
                if "POLICY" in str(n.get("type") or "").upper()
                or "IAM" in str(n.get("type") or "").upper()
            ]
        )
        resource_nodes = _node_ids(
            [n for n in raw_nodes if "RESOURCE" in str(n.get("type") or "").upper()]
        )
        return {
            "root_cause_node": _optional_str(
                data.get("root_cause_node") or data.get("root_node_id")
            ),
            "nodes": nodes,
            "edges": edges,
            "artifact_nodes": artifact_nodes,
            "policy_nodes": policy_nodes,
            "resource_nodes": resource_nodes,
            "consistency_status": _optional_str(data.get("consistency_status")),
            "warnings": [str(w) for w in _as_list(data.get("warnings"))],
            "missing_links": [str(m) for m in _as_list(data.get("missing_links"))],
        }

    def _collect_artifacts(
        self,
        options: dict[str, Any],
        hypothesis: dict[str, Any],
    ) -> dict[str, Any]:
        bundle = _as_dict(options.get("artifact_bundle") or options.get("artifacts"))
        parse_results = _sorted_dicts(
            _as_list(options.get("parse_results") or bundle.get("parse_results") or [])
        )
        affected = hypothesis.get("affected_artifact") or bundle.get("affected_artifact")
        affected_dict = (
            _as_dict(affected)
            if isinstance(affected, dict)
            else ({"id": affected} if isinstance(affected, str) else None)
        )

        entities: list[dict[str, Any]] = []
        for result in parse_results:
            entities.extend(
                _sorted_dicts(_as_list(result.get("entities") or result.get("structured_entities")))
            )
        entities = entities[: self._max_graph_nodes]

        fragment = None
        source_path = None
        line_range = None
        quality = None
        if affected_dict:
            source_path = _optional_str(
                affected_dict.get("source_path") or affected_dict.get("path")
            )
            line_range = affected_dict.get("line_range")
            raw_fragment = affected_dict.get("current_configuration_fragment") or affected_dict.get(
                "source_fragment"
            )
            if isinstance(raw_fragment, str) and raw_fragment.strip():
                fragment = raw_fragment
            quality = _optional_float(
                affected_dict.get("quality") or affected_dict.get("artifact_quality")
            )

        changed_files = sorted(
            {
                str(p)
                for p in _as_list(
                    options.get("changed_files")
                    or bundle.get("changed_files")
                    or hypothesis.get("changed_files")
                )
                if p
            }
        )
        return {
            "affected_artifact": affected_dict or affected,
            "source_path": source_path,
            "line_range": line_range,
            "parser_entities": entities,
            "current_configuration_fragment": fragment,
            "related_changed_files": changed_files,
            "previous_successful_version": _optional_str(
                options.get("previous_successful_version")
                or bundle.get("previous_successful_version")
            ),
            "artifact_quality": quality,
        }

    def _missing_artifacts(
        self,
        artifacts: dict[str, Any],
        hypothesis: dict[str, Any],
    ) -> list[str]:
        missing: list[str] = []
        if not artifacts.get("affected_artifact") and not artifacts.get("parser_entities"):
            missing.append("affected_artifact")
        if not artifacts.get("current_configuration_fragment") and hypothesis.get(
            "requires_configuration_fragment", True
        ):
            missing.append("current_configuration_fragment")
        category = str(hypothesis.get("category_code") or hypothesis.get("category") or "").lower()
        if "iam" in category or "permission" in category:
            has_policy = any(
                "POLICY" in str(e.get("type") or "").upper()
                or "IAM" in str(e.get("type") or "").upper()
                for e in artifacts.get("parser_entities") or []
            )
            if not has_policy and not artifacts.get("current_configuration_fragment"):
                missing.append("iam_or_policy_artifact")
        return sorted(set(missing))

    def _estimate_size(self, ctx: CounterfactualRemediationContext) -> int:
        try:
            return len(json.dumps(ctx.to_dict(), default=str))
        except (TypeError, ValueError):
            return 0
