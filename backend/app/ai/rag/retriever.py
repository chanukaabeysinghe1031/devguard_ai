"""Knowledge retriever — query → embed → search → rerank → context selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.ai.orchestration.analysis_context import AnalysisContext
from app.ai.rag.query_builder import build_retrieval_query
from app.ai.rag.reranker import rerank_hits
from app.domain.interfaces.ai_providers import EmbeddingProvider, VectorStore
from app.domain.services.secret_masker import mask_secrets


@dataclass
class RetrievedChunkCandidate:
    chunk_id: UUID
    rank: int
    similarity_score: float
    content: str
    title: str | None = None
    source_url: str | None = None
    provider: str | None = None
    used_in_reasoning: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeRetriever:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        retrieve_k: int = 10,
        context_k: int = 5,
    ) -> None:
        self._embeddings = embedding_provider
        self._store = vector_store
        self._retrieve_k = retrieve_k
        self._context_k = context_k

    def retrieve(self, context: AnalysisContext) -> list[RetrievedChunkCandidate]:
        query = build_retrieval_query(context)
        masked_query, _ = mask_secrets(query)
        embedding = self._embeddings.embed([masked_query])[0]
        where = _metadata_filters(context)
        hits = self._store.query(
            embedding=embedding,
            top_k=self._retrieve_k,
            where=where or None,
        )
        if not hits and where:
            # Soften filters if too restrictive.
            hits = self._store.query(embedding=embedding, top_k=self._retrieve_k, where=None)
        ranked = rerank_hits(masked_query, hits, top_k=self._context_k)

        candidates: list[RetrievedChunkCandidate] = []
        for idx, hit in enumerate(ranked, start=1):
            try:
                chunk_uuid = UUID(str(hit.chunk_id))
            except ValueError:
                continue
            masked_content, _ = mask_secrets(hit.text)
            candidates.append(
                RetrievedChunkCandidate(
                    chunk_id=chunk_uuid,
                    rank=idx,
                    similarity_score=round(float(hit.score), 6),
                    content=masked_content,
                    title=str(hit.metadata.get("title") or "") or None,
                    source_url=str(hit.metadata.get("source_url") or "") or None,
                    provider=str(hit.metadata.get("provider") or "") or None,
                    used_in_reasoning=idx <= self._context_k,
                    metadata=dict(hit.metadata),
                )
            )
        context.retrieved_chunks = candidates
        context.retrieval_backend = self._store.name
        context.embedding_provider_name = self._embeddings.name
        if not candidates:
            context.warnings.append("RAG retrieved no knowledge chunks.")
            context.partial = True
        return candidates


def _metadata_filters(context: AnalysisContext) -> dict[str, Any]:
    filters: dict[str, Any] = {"document_status": "active"}
    provider = (context.signals or {}).get("provider")
    if provider:
        filters["provider"] = str(provider).lower()
    return filters
