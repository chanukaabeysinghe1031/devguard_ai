"""Session-level source deduplication for hypothesis retrieval."""

from __future__ import annotations

import hashlib
import re

from app.domain.hypothesis_retrieval.models import HypothesisRetrievedItem

_WS = re.compile(r"\s+")


def normalized_content_hash(text: str) -> str:
    normalised = _WS.sub(" ", (text or "").strip().lower())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def _identity_keys(item: HypothesisRetrievedItem) -> list[str]:
    keys: list[str] = []
    if item.source_id:
        keys.append(f"source:{item.source_type.value}:{item.source_id}")
    if item.document_id and item.chunk_id:
        keys.append(f"doc:{item.document_id}:{item.chunk_id}")
    elif item.document_id:
        keys.append(f"doc:{item.document_id}")
    if item.artifact_id and item.source_path:
        loc = f"{item.line_start or ''}:{item.line_end or ''}"
        keys.append(f"artifact:{item.artifact_id}:{item.source_path}:{loc}")
    elif item.artifact_id:
        keys.append(f"artifact:{item.artifact_id}")
    if item.graph_node_id:
        keys.append(f"graph_node:{item.graph_node_id}")
    if item.graph_edge_id:
        keys.append(f"graph_edge:{item.graph_edge_id}")
    if item.temporal_event_id:
        keys.append(f"temporal:{item.temporal_event_id}")
    if item.historical_incident_id:
        keys.append(f"hist:{item.historical_incident_id}")
    digest = item.normalized_text_hash or normalized_content_hash(item.text_excerpt[:400])
    keys.append(f"hash:{digest}")
    return keys


def deduplicate_session_items(
    items: list[HypothesisRetrievedItem],
) -> tuple[list[HypothesisRetrievedItem], int]:
    """Keep strongest representation; merge query associations and adapters."""
    if not items:
        return [], 0

    ordered = sorted(
        items,
        key=lambda i: (
            -float(i.retrieval_score),
            i.source_type.value,
            i.query_id,
            i.rank_within_query,
        ),
    )
    kept: list[HypothesisRetrievedItem] = []
    key_to_index: dict[str, int] = {}
    duplicates = 0

    for item in ordered:
        if not item.normalized_text_hash:
            item.normalized_text_hash = normalized_content_hash(item.text_excerpt[:400])
        if item.query_id and item.query_id not in item.associated_query_ids:
            item.associated_query_ids.append(item.query_id)
        if item.adapter_name and item.adapter_name not in item.contributing_adapters:
            item.contributing_adapters.append(item.adapter_name)

        keys = _identity_keys(item)
        existing_idx: int | None = None
        for key in keys:
            if key in key_to_index:
                existing_idx = key_to_index[key]
                break

        if existing_idx is None:
            idx = len(kept)
            kept.append(item)
            for key in keys:
                key_to_index[key] = idx
            continue

        duplicates += 1
        existing = kept[existing_idx]
        for qid in item.associated_query_ids:
            if qid not in existing.associated_query_ids:
                existing.associated_query_ids.append(qid)
        for adapter in item.contributing_adapters:
            if adapter not in existing.contributing_adapters:
                existing.contributing_adapters.append(adapter)
        if item.retrieval_score > existing.retrieval_score:
            # Preserve stronger scores while keeping associations already merged.
            existing.retrieval_score = item.retrieval_score
            if item.lexical_score is not None:
                existing.lexical_score = item.lexical_score
            if item.vector_score is not None:
                existing.vector_score = item.vector_score
            if item.historical_score is not None:
                existing.historical_score = item.historical_score
            if item.graph_distance is not None:
                existing.graph_distance = item.graph_distance
            existing.adapter_name = item.adapter_name
            existing.rank_within_query = item.rank_within_query
            existing.query_id = item.query_id
        for key in keys:
            key_to_index[key] = existing_idx

    for order, item in enumerate(kept, start=1):
        item.global_session_order = order
    return kept, duplicates
