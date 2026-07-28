"""Vector store implementations — in-memory (default) and optional ChromaDB."""

from __future__ import annotations

import math
from typing import Any

from app.domain.interfaces.ai_providers import EmbeddedChunk, VectorHit, VectorStore


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class InMemoryVectorStore(VectorStore):
    """Process-local vector index for deterministic offline RAG."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[list[float], EmbeddedChunk]] = {}

    @property
    def name(self) -> str:
        return "memory"

    def upsert(self, chunks: list[EmbeddedChunk], embeddings: list[list[float]]) -> None:
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            self._items[chunk.chunk_id] = (embedding, chunk)

    def query(
        self,
        *,
        embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        scored: list[VectorHit] = []
        for chunk_id, (vec, chunk) in self._items.items():
            if where:
                mismatch = False
                for key, expected in where.items():
                    if chunk.metadata.get(key) != expected:
                        mismatch = True
                        break
                if mismatch:
                    continue
            scored.append(
                VectorHit(
                    chunk_id=chunk_id,
                    score=_cosine(embedding, vec),
                    text=chunk.text,
                    metadata=dict(chunk.metadata),
                )
            )
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:top_k]


class ChromaVectorStore(VectorStore):
    """Optional ChromaDB-backed vector store (architecture-approved)."""

    def __init__(self, *, persist_path: str, collection_name: str = "devguard_knowledge") -> None:
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("chromadb is required for RAG_BACKEND=chroma") from exc
        client = chromadb.PersistentClient(path=persist_path)
        self._collection = client.get_or_create_collection(name=collection_name)
        self._persist_path = persist_path

    @property
    def name(self) -> str:
        return f"chroma:{self._persist_path}"

    def upsert(self, chunks: list[EmbeddedChunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        self._collection.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=embeddings,
            documents=[c.text for c in chunks],
            metadatas=[c.metadata for c in chunks],
        )

    def query(
        self,
        *,
        embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where or None,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[VectorHit] = []
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        for chunk_id, doc, meta, dist in zip(ids, docs, metas, dists, strict=False):
            score = 1.0 / (1.0 + float(dist)) if dist is not None else 0.0
            hits.append(
                VectorHit(
                    chunk_id=str(chunk_id),
                    score=score,
                    text=str(doc or ""),
                    metadata=dict(meta or {}),
                )
            )
        return hits


# Shared process-local store so ingestion and retrieval share state in memory mode.
_MEMORY_STORE = InMemoryVectorStore()


def get_shared_memory_store() -> InMemoryVectorStore:
    return _MEMORY_STORE


def build_vector_store(backend: str, *, persist_path: str) -> VectorStore:
    if backend == "chroma":
        return ChromaVectorStore(persist_path=persist_path)
    return get_shared_memory_store()
