"""Lightweight keyword reranker for hybrid retrieval ranking."""

from __future__ import annotations

import re

from app.domain.interfaces.ai_providers import VectorHit

_WORD = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


def rerank_hits(query: str, hits: list[VectorHit], *, top_k: int) -> list[VectorHit]:
    query_tokens = set(_WORD.findall(query.lower()))
    if not query_tokens:
        return hits[:top_k]

    rescored: list[VectorHit] = []
    for hit in hits:
        doc_tokens = set(_WORD.findall(hit.text.lower()))
        overlap = len(query_tokens & doc_tokens) / max(1, len(query_tokens))
        combined = 0.7 * hit.score + 0.3 * overlap
        rescored.append(
            VectorHit(
                chunk_id=hit.chunk_id,
                score=combined,
                text=hit.text,
                metadata=dict(hit.metadata),
            )
        )
    rescored.sort(key=lambda item: item.score, reverse=True)
    return rescored[:top_k]
