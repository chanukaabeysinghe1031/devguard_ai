"""Citation helpers for retrieved knowledge chunks."""

from __future__ import annotations

from app.ai.orchestration.analysis_context import AnalysisContext
from app.ai.rag.retriever import RetrievedChunkCandidate


def mark_used_chunks(
    context: AnalysisContext,
    chunk_ids: list[str],
) -> list[RetrievedChunkCandidate]:
    allowed = {str(cid) for cid in chunk_ids}
    for chunk in context.retrieved_chunks:
        chunk.used_in_reasoning = str(chunk.chunk_id) in allowed
    return context.retrieved_chunks


def citation_payload(context: AnalysisContext) -> list[dict]:
    return [
        {
            "chunk_id": str(chunk.chunk_id),
            "rank": chunk.rank,
            "similarity_score": chunk.similarity_score,
            "title": chunk.title,
            "source_url": chunk.source_url,
            "provider": chunk.provider,
            "used_in_reasoning": chunk.used_in_reasoning,
            "content": chunk.content[:600],
        }
        for chunk in context.retrieved_chunks
    ]
