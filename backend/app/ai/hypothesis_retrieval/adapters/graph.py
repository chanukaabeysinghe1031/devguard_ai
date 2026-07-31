"""Deterministic graph evidence adapter (no embeddings)."""

from __future__ import annotations

import contextlib
import time
from typing import Any

from app.ai.hypothesis_retrieval.dedupe import normalized_content_hash
from app.domain.hypothesis_retrieval.enums import (
    HypothesisRetrievalSourceType,
    RetrievalFailureType,
    RetrievalItemRelation,
)
from app.domain.hypothesis_retrieval.models import (
    HypothesisRetrievalAdapterResult,
    HypothesisRetrievalContext,
    HypothesisRetrievalQuerySpec,
    HypothesisRetrievedItem,
)
from app.domain.services.secret_masker import mask_secrets

ADAPTER_NAME = "graph_evidence"
ADAPTER_VERSION = "v1"


class GraphEvidenceRetrievalAdapter:
    adapter_name = ADAPTER_NAME
    adapter_version = ADAPTER_VERSION
    supported_source_types = [HypothesisRetrievalSourceType.GRAPH]

    def __init__(self, *, enabled: bool = True, max_items: int = 40) -> None:
        self._enabled = enabled
        self._max_items = max(1, max_items)

    def is_available(self) -> bool:
        return self._enabled

    def health_status(self) -> dict[str, Any]:
        return {"available": self.is_available(), "enabled": self._enabled}

    def configuration_summary(self) -> dict[str, Any]:
        return {
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "max_items": self._max_items,
        }

    def retrieve(
        self,
        context: HypothesisRetrievalContext,
        query_spec: HypothesisRetrievalQuerySpec,
    ) -> HypothesisRetrievalAdapterResult:
        started = time.perf_counter()
        if not self.is_available():
            return HypothesisRetrievalAdapterResult(
                adapter_name=self.adapter_name,
                adapter_version=self.adapter_version,
                source_type=HypothesisRetrievalSourceType.GRAPH,
                query_id=query_spec.query_id,
                status="SOURCE_UNAVAILABLE",
                failure_type=RetrievalFailureType.SOURCE_UNAVAILABLE,
                errors=["graph_adapter_disabled"],
                duration_ms=int((time.perf_counter() - started) * 1000),
            )

        needle = (query_spec.normalized_query or "").lower()
        target_nodes = set(query_spec.graph_node_ids or [])
        constraints = (query_spec.metadata or {}).get("graph_constraints")
        max_nodes = self._max_items
        max_edges = self._max_items
        if isinstance(constraints, dict):
            start_ids = constraints.get("start_node_ids")
            if isinstance(start_ids, list):
                target_nodes.update(str(x) for x in start_ids if x)
            if constraints.get("max_nodes"):
                with contextlib.suppress(TypeError, ValueError):
                    max_nodes = max(1, min(self._max_items, int(constraints["max_nodes"])))
            if constraints.get("max_edges"):
                with contextlib.suppress(TypeError, ValueError):
                    max_edges = max(1, min(self._max_items, int(constraints["max_edges"])))
        if context.root_cause_node_id:
            target_nodes.add(context.root_cause_node_id)
        if context.observed_failure_node_id:
            target_nodes.add(context.observed_failure_node_id)
        target_nodes.update(context.causal_path_node_ids)

        items: list[HypothesisRetrievedItem] = []
        rank = 0

        for node in context.graph_neighborhood_nodes[:max_nodes]:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("stable_key") or node.get("node_id") or node.get("id") or "")
            label = str(node.get("label") or "")
            node_type = str(node.get("node_type") or "")
            text = f"graph_node id={node_id} type={node_type} label={label}"
            off_target = bool(target_nodes and node_id and node_id not in target_nodes)
            if (
                off_target
                and query_spec.query_type.value != "GRAPH_NEIGHBORHOOD"
                and needle
                and needle not in text.lower()
            ):
                continue
            if (
                not off_target
                and needle
                and needle not in text.lower()
                and node_id not in target_nodes
            ):
                continue
            rank += 1
            if node_id and node_id in {
                context.root_cause_node_id,
                context.observed_failure_node_id,
            }:
                distance = 0.0
            elif node_id in context.causal_path_node_ids:
                distance = 1.0
            else:
                distance = 2.0
            items.append(
                self._item(
                    context,
                    query_spec,
                    text=text,
                    graph_node_id=node_id or None,
                    source_path=str(node.get("source_path") or "") or None,
                    line_start=_as_int(node.get("line_start")),
                    line_end=_as_int(node.get("line_end")),
                    title=label or node_type or "graph_node",
                    score=max(0.2, 1.0 - (distance * 0.2)),
                    distance=distance,
                    rank=rank,
                )
            )

        for edge in context.graph_neighborhood_edges[:max_edges]:
            if not isinstance(edge, dict):
                continue
            edge_id = str(edge.get("stable_key") or edge.get("edge_id") or edge.get("id") or "")
            edge_type = str(edge.get("edge_type") or "")
            explanation = str(edge.get("explanation") or "")
            text = f"graph_edge id={edge_id} type={edge_type} {explanation}".strip()
            if needle and needle not in text.lower():
                continue
            rank += 1
            items.append(
                self._item(
                    context,
                    query_spec,
                    text=text,
                    graph_edge_id=edge_id or None,
                    title=edge_type or "graph_edge",
                    score=0.45,
                    distance=1.0,
                    rank=rank,
                )
            )

        for warning in sorted(context.graph_warnings)[:5]:
            rank += 1
            items.append(
                self._item(
                    context,
                    query_spec,
                    text=f"graph_warning={warning}",
                    title="graph_warning",
                    score=0.25,
                    distance=3.0,
                    rank=rank,
                    relation=RetrievalItemRelation.CONTEXT,
                )
            )

        limited = items[: query_spec.top_k]
        return HypothesisRetrievalAdapterResult(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            source_type=HypothesisRetrievalSourceType.GRAPH,
            query_id=query_spec.query_id,
            status="COMPLETE" if limited else "NO_EVIDENCE",
            raw_result_count=len(items),
            items=limited,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    def _item(
        self,
        context: HypothesisRetrievalContext,
        query_spec: HypothesisRetrievalQuerySpec,
        *,
        text: str,
        score: float,
        distance: float,
        rank: int,
        graph_node_id: str | None = None,
        graph_edge_id: str | None = None,
        source_path: str | None = None,
        line_start: int | None = None,
        line_end: int | None = None,
        title: str | None = None,
        relation: RetrievalItemRelation | None = None,
    ) -> HypothesisRetrievedItem:
        masked, _ = mask_secrets(text)
        return HypothesisRetrievedItem(
            source_type=HypothesisRetrievalSourceType.GRAPH,
            source_system="evidence_graph",
            text_excerpt=masked[:1500],
            query_id=query_spec.query_id,
            hypothesis_id=context.hypothesis_id,
            source_id=graph_node_id or graph_edge_id,
            graph_node_id=graph_node_id,
            graph_edge_id=graph_edge_id,
            title=title,
            normalized_text_hash=normalized_content_hash(masked[:400]),
            source_path=source_path,
            line_start=line_start,
            line_end=line_end,
            retrieval_score=score,
            graph_distance=distance,
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            relation_candidate=relation
            or query_spec.expected_relation
            or RetrievalItemRelation.CONTEXT,
            rank_within_query=rank,
            associated_query_ids=[query_spec.query_id],
            contributing_adapters=[self.adapter_name],
            redaction_status="masked",
        )


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
