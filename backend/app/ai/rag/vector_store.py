"""Vector store implementations — in-memory (default) and optional ChromaDB."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Literal

from app.domain.interfaces.ai_providers import EmbeddedChunk, VectorHit, VectorStore


class CollectionCompatibilityError(RuntimeError):
    """Existing Chroma collection is incompatible with the configured embedding identity."""


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def _metadata_matches(metadata: dict[str, Any], where: dict[str, Any] | None) -> bool:
    """Match Chroma-style where filters used by product/historical retrievers."""
    if not where:
        return True
    if "$and" in where:
        clauses = where.get("$and") or []
        return all(
            isinstance(clause, dict) and _metadata_matches(metadata, clause) for clause in clauses
        )
    if "$or" in where:
        clauses = where.get("$or") or []
        return any(
            isinstance(clause, dict) and _metadata_matches(metadata, clause) for clause in clauses
        )
    for key, expected in where.items():
        actual = metadata.get(key)
        if isinstance(expected, dict):
            if "$eq" in expected and actual != expected["$eq"]:
                return False
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            continue
        if actual != expected:
            return False
    return True


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
            if not _metadata_matches(dict(chunk.metadata or {}), where):
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


ChromaHealthStatus = Literal[
    "unavailable",
    "healthy_uninitialised",
    "healthy_ready",
]


@dataclass(frozen=True)
class ChromaHealthResult:
    """Safe Chroma connectivity summary — never includes secrets."""

    status: ChromaHealthStatus
    detail: str
    collection_name: str
    collection_count: int | None = None
    heartbeat_ns: int | None = None


class ChromaVectorStore(VectorStore):
    """Optional ChromaDB-backed vector store (architecture-approved).

    Modes:
    - HTTP client when ``host`` is set (Docker Compose: host=chroma, port=8000)
    - PersistentClient when ``host`` is empty (local path under CHROMA_PERSIST_PATH)

    Does not delete/reset/recreate collections on startup. Collection creation happens
    only via get_or_create during upsert (ingestion). Health checks never create
    collections.
    """

    def __init__(
        self,
        *,
        persist_path: str = "./storage/chroma",
        collection_name: str = "devguard_knowledge",
        host: str = "",
        port: int = 8000,
        tenant: str = "default_tenant",
        database: str = "default_database",
        connect_retries: int = 5,
        connect_retry_delay_s: float = 1.0,
        embedding_identity: dict[str, str] | None = None,
    ) -> None:
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("chromadb is required for RAG_BACKEND=chroma") from exc

        self._collection_name = collection_name
        self._persist_path = persist_path
        self._host = (host or "").strip()
        self._port = int(port)
        self._tenant = tenant
        self._database = database
        self._embedding_identity = dict(embedding_identity or {})
        self._collection = None

        last_error: Exception | None = None
        attempts = max(1, connect_retries)
        for attempt in range(1, attempts + 1):
            try:
                if self._host:
                    self._client = chromadb.HttpClient(
                        host=self._host,
                        port=self._port,
                        tenant=self._tenant,
                        database=self._database,
                    )
                    # Bounded connectivity probe — no collection mutation.
                    self._client.heartbeat()
                else:
                    self._client = chromadb.PersistentClient(path=persist_path)
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001 - bounded startup retry
                last_error = exc
                if attempt >= attempts:
                    break
                time.sleep(connect_retry_delay_s)
        if last_error is not None:
            raise RuntimeError(
                f"Unable to connect to Chroma after {attempts} attempt(s): {last_error}"
            ) from last_error

    @property
    def name(self) -> str:
        if self._host:
            return f"chroma-http://{self._host}:{self._port}/{self._collection_name}"
        return f"chroma:{self._persist_path}"

    @property
    def collection_name(self) -> str:
        return self._collection_name

    def _get_existing_collection(self) -> Any | None:
        try:
            return self._client.get_collection(name=self._collection_name)
        except Exception:  # noqa: BLE001 - missing collection is a normal state
            return None

    def _collection_metadata(self, collection: Any) -> dict[str, Any]:
        meta = getattr(collection, "metadata", None) or {}
        return dict(meta) if isinstance(meta, dict) else {}

    def _assert_compatible(self, collection: Any, *, vector_dim: int | None) -> None:
        """Raise when an existing non-empty collection conflicts with configured identity."""
        meta = self._collection_metadata(collection)
        identity = self._embedding_identity
        if not identity and vector_dim is None:
            return

        stored_hash = str(meta.get("devguard_embedding_config_hash") or "")
        stored_dim = str(meta.get("devguard_embedding_dimension") or "")
        stored_model = str(meta.get("devguard_embedding_model") or "")
        stored_provider = str(meta.get("devguard_embedding_provider") or "")

        if identity:
            expected_hash = identity.get("devguard_embedding_config_hash", "")
            if stored_hash and expected_hash and stored_hash != expected_hash:
                raise CollectionCompatibilityError(
                    "Chroma collection embedding identity mismatch for "
                    f"'{self._collection_name}'. Stored provider/model/dimension "
                    f"({stored_provider}/{stored_model}/{stored_dim}) does not match "
                    "the configured embedding provider. Re-run knowledge ingestion "
                    "with --recreate when explicitly approved; collections are never "
                    "deleted automatically."
                )
            expected_dim = identity.get("devguard_embedding_dimension")
            if stored_dim and expected_dim and stored_dim != expected_dim:
                raise CollectionCompatibilityError(
                    f"Chroma collection '{self._collection_name}' dimension "
                    f"{stored_dim} is incompatible with configured dimension "
                    f"{expected_dim}. Use explicit --recreate to rebuild."
                )

        if vector_dim is not None and stored_dim and stored_dim != str(vector_dim):
            raise CollectionCompatibilityError(
                f"Chroma collection '{self._collection_name}' stores dimension "
                f"{stored_dim} but incoming vectors have dimension {vector_dim}."
            )

    def _ensure_collection_for_write(self, *, vector_dim: int | None = None) -> Any:
        """Resolve collection for upsert only — never deletes or resets."""
        if self._collection is not None:
            try:
                count = int(self._collection.count())
            except Exception:  # noqa: BLE001
                count = 0
            if count > 0:
                self._assert_compatible(self._collection, vector_dim=vector_dim)
            return self._collection

        existing = self._get_existing_collection()
        if existing is not None:
            try:
                count = int(existing.count())
            except Exception:  # noqa: BLE001
                count = 0
            if count > 0:
                self._assert_compatible(existing, vector_dim=vector_dim)
            elif self._embedding_identity:
                # Empty existing collection — attach identity metadata when possible.
                try:
                    merged = {**self._collection_metadata(existing), **self._embedding_identity}
                    existing.modify(metadata=merged)
                except Exception:  # noqa: BLE001 - metadata update is best-effort
                    pass
            self._collection = existing
            return self._collection

        metadata: dict[str, Any] = {"hnsw:space": "cosine"}
        metadata.update(self._embedding_identity)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata=metadata,
        )
        return self._collection

    def upsert(self, chunks: list[EmbeddedChunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")
        vector_dim = len(embeddings[0]) if embeddings and embeddings[0] else None
        if vector_dim is not None:
            for vector in embeddings:
                if len(vector) != vector_dim:
                    raise ValueError("all embeddings must share the same dimension")
        collection = self._ensure_collection_for_write(vector_dim=vector_dim)
        # Chroma metadata values must be scalar.
        metadatas: list[dict[str, Any]] = []
        for chunk in chunks:
            meta: dict[str, Any] = {}
            for key, value in (chunk.metadata or {}).items():
                if isinstance(value, (str, int, float, bool)) or value is None:
                    meta[key] = value if value is not None else ""
                else:
                    meta[key] = str(value)
            metadatas.append(meta)
        collection.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=embeddings,
            documents=[c.text for c in chunks],
            metadatas=metadatas,
        )

    def query(
        self,
        *,
        embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        collection = self._collection or self._get_existing_collection()
        if collection is None:
            return []
        self._collection = collection
        result = collection.query(
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

    def delete_collection(self) -> None:
        """Explicitly delete this store's collection. Never called on startup."""
        try:
            self._client.delete_collection(name=self._collection_name)
        finally:
            self._collection = None

    def check_health(self) -> ChromaHealthResult:
        """Non-destructive connectivity check. Never returns secrets."""
        try:
            heartbeat = int(self._client.heartbeat())
        except Exception as exc:  # noqa: BLE001 - surface availability cleanly
            return ChromaHealthResult(
                status="unavailable",
                detail=f"Chroma heartbeat failed: {type(exc).__name__}",
                collection_name=self._collection_name,
            )

        collection = self._get_existing_collection()
        if collection is None:
            return ChromaHealthResult(
                status="healthy_uninitialised",
                detail="Chroma healthy; knowledge collection not initialised",
                collection_name=self._collection_name,
                heartbeat_ns=heartbeat,
            )

        try:
            count = int(collection.count())
        except Exception:  # noqa: BLE001
            count = None
        return ChromaHealthResult(
            status="healthy_ready",
            detail="Chroma healthy; knowledge collection ready",
            collection_name=self._collection_name,
            collection_count=count,
            heartbeat_ns=heartbeat,
        )


# Shared process-local store so ingestion and retrieval share state in memory mode.
_MEMORY_STORE = InMemoryVectorStore()


def get_shared_memory_store() -> InMemoryVectorStore:
    return _MEMORY_STORE


def build_vector_store(
    backend: str,
    *,
    persist_path: str,
    host: str = "",
    port: int = 8000,
    collection_name: str = "devguard_knowledge",
    tenant: str = "default_tenant",
    database: str = "default_database",
    embedding_identity: dict[str, str] | None = None,
) -> VectorStore:
    if backend == "chroma":
        return ChromaVectorStore(
            persist_path=persist_path,
            collection_name=collection_name,
            host=host,
            port=port,
            tenant=tenant,
            database=database,
            embedding_identity=embedding_identity,
        )
    return get_shared_memory_store()
