"""Reference and causal-path validators for hypotheses (Phase 6A.4)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.classification.taxonomy_registry import (
    FailureTaxonomyRegistry,
    get_taxonomy_registry,
)
from app.domain.hypotheses.enums import CausalPathValidationStatus, HypothesisStatus
from app.domain.hypotheses.models import CausalHypothesis, HypothesisGenerationContext
from app.domain.hypotheses.templates import DOWNSTREAM_SYMPTOM_TOKENS


@dataclass(slots=True)
class ReferenceValidationResult:
    accepted: bool
    hypothesis: CausalHypothesis
    rejected_reasons: list[str] = field(default_factory=list)


class HypothesisReferenceValidator:
    def __init__(self, *, registry: FailureTaxonomyRegistry | None = None) -> None:
        self._registry = registry or get_taxonomy_registry()

    def validate(
        self, hypothesis: CausalHypothesis, context: HypothesisGenerationContext
    ) -> ReferenceValidationResult:
        reasons: list[str] = []
        node_ids = {
            str(n.get("stable_key") or n.get("id") or "")
            for n in context.relevant_graph_nodes
            if n.get("stable_key") or n.get("id")
        }
        edge_ids = {
            str(e.get("id") or e.get("stable_key") or "")
            for e in context.relevant_graph_edges
            if e.get("id") or e.get("stable_key")
        }
        evidence_ids = {
            str(e.get("id") or "") for e in context.evidence_candidates if e.get("id")
        }
        artifact_ids = set(context.artifact_availability)

        if hypothesis.category_code and not self._registry.is_valid_category(
            hypothesis.category_code
        ):
            reasons.append(f"invalid_category:{hypothesis.category_code}")

        root_id = hypothesis.root_cause_node_id
        if root_id and node_ids and root_id not in node_ids:
            # Allow temporal event IDs even if not in graph node set.
            temporal_id = (context.temporal_primary_failure or {}).get(
                "primary_failure_event_id"
            )
            if root_id != temporal_id:
                reasons.append(f"unknown_root_cause_node:{root_id}")

        if (
            hypothesis.observed_failure_node_id
            and node_ids
            and hypothesis.observed_failure_node_id not in node_ids
        ):
            temporal_id = (context.temporal_primary_failure or {}).get("primary_failure_event_id")
            if hypothesis.observed_failure_node_id != temporal_id:
                reasons.append(
                    f"unknown_observed_failure_node:{hypothesis.observed_failure_node_id}"
                )

        for nid in hypothesis.causal_path_node_ids:
            if node_ids and nid not in node_ids:
                temporal_id = (context.temporal_primary_failure or {}).get(
                    "primary_failure_event_id"
                )
                if nid != temporal_id:
                    reasons.append(f"unknown_path_node:{nid}")

        for eid in hypothesis.causal_path_edge_ids:
            if edge_ids and eid not in edge_ids:
                reasons.append(f"unknown_path_edge:{eid}")

        for link in hypothesis.evidence_links:
            if link.evidence_item_id and evidence_ids and link.evidence_item_id not in evidence_ids:
                reasons.append(f"unknown_evidence_id:{link.evidence_item_id}")
            if link.graph_node_id and node_ids and link.graph_node_id not in node_ids:
                reasons.append(f"unknown_link_node:{link.graph_node_id}")
            if link.graph_edge_id and edge_ids and link.graph_edge_id not in edge_ids:
                reasons.append(f"unknown_link_edge:{link.graph_edge_id}")
            if link.artifact_id and artifact_ids and link.artifact_id not in artifact_ids:
                reasons.append(f"unknown_artifact_id:{link.artifact_id}")

        # Reject secret-looking values in claim text.
        lowered = hypothesis.causal_claim.lower()
        if any(tok in lowered for tok in ("-----begin", "aws_secret", "password=", "token=")):
            reasons.append("possible_secret_in_claim")

        # Root cause should not be a pure downstream symptom unless justified.
        if hypothesis.root_cause_node_id:
            for node in context.relevant_graph_nodes:
                key = str(node.get("stable_key") or node.get("id") or "")
                if key != hypothesis.root_cause_node_id:
                    continue
                label = str(node.get("label") or "").lower()
                if any(tok in label for tok in DOWNSTREAM_SYMPTOM_TOKENS):
                    temporal = context.temporal_primary_failure or {}
                    if temporal.get("primary_failure_event_id") and temporal.get(
                        "primary_failure_event_id"
                    ) != key:
                        reasons.append("root_cause_is_downstream_symptom")

        if reasons:
            hypothesis.status = HypothesisStatus.INVALID
            hypothesis.warnings.extend(reasons)
            return ReferenceValidationResult(False, hypothesis, reasons)
        return ReferenceValidationResult(True, hypothesis, [])


class HypothesisCausalPathValidator:
    def validate(
        self, hypothesis: CausalHypothesis, context: HypothesisGenerationContext
    ) -> CausalHypothesis:
        nodes = hypothesis.causal_path_node_ids
        edges = hypothesis.causal_path_edge_ids
        if not nodes and not edges:
            hypothesis.path_validation_status = CausalPathValidationStatus.NOT_APPLICABLE
            if hypothesis.root_cause_node_id and hypothesis.observed_failure_node_id:
                hypothesis.path_validation_status = CausalPathValidationStatus.PARTIAL
                hypothesis.path_validation_warnings.append("path_nodes_not_provided")
                if hypothesis.status == HypothesisStatus.GENERATED:
                    hypothesis.status = HypothesisStatus.INCOMPLETE
            return hypothesis

        edge_map = {
            str(e.get("id") or e.get("stable_key") or ""): e
            for e in context.relevant_graph_edges
            if e.get("id") or e.get("stable_key")
        }
        warnings: list[str] = []
        connected = True
        for eid in edges:
            edge = edge_map.get(eid)
            if edge is None:
                connected = False
                warnings.append(f"missing_edge:{eid}")
                continue
            src = str(edge.get("source_node_id") or edge.get("source") or "")
            tgt = str(edge.get("target_node_id") or edge.get("target") or "")
            if nodes and src not in nodes and tgt not in nodes:
                connected = False
                warnings.append(f"edge_not_in_path_nodes:{eid}")
            derivation = str(edge.get("derivation_type") or edge.get("derivation") or "").upper()
            if "HEURISTIC" in derivation or "INFERRED" in derivation:
                warnings.append(f"heuristic_edge:{eid}")

        # Reachability check when both endpoints present.
        if (
            hypothesis.root_cause_node_id
            and hypothesis.observed_failure_node_id
            and hypothesis.root_cause_node_id in nodes
            and hypothesis.observed_failure_node_id in nodes
            and edges
        ):
            adj: dict[str, set[str]] = {n: set() for n in nodes}
            for eid in edges:
                edge = edge_map.get(eid)
                if not edge:
                    continue
                src = str(edge.get("source_node_id") or edge.get("source") or "")
                tgt = str(edge.get("target_node_id") or edge.get("target") or "")
                if src in adj and tgt in adj:
                    adj[src].add(tgt)
            seen = {hypothesis.root_cause_node_id}
            stack = [hypothesis.root_cause_node_id]
            while stack:
                cur = stack.pop()
                for nxt in adj.get(cur, set()):
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            if hypothesis.observed_failure_node_id not in seen:
                connected = False
                warnings.append("root_cannot_reach_observed_failure")

        if not connected:
            hypothesis.path_validation_status = CausalPathValidationStatus.INVALID
            if hypothesis.status not in {HypothesisStatus.INVALID, HypothesisStatus.REJECTED}:
                hypothesis.status = HypothesisStatus.INCOMPLETE
        elif warnings:
            hypothesis.path_validation_status = CausalPathValidationStatus.VALID_WITH_WARNINGS
        else:
            hypothesis.path_validation_status = CausalPathValidationStatus.VALID
        hypothesis.path_validation_warnings.extend(warnings)
        return hypothesis
