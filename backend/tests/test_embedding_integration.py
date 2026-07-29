"""Real sentence-transformer + Chroma integration tests (marked, session-scoped model)."""

from __future__ import annotations

import contextlib
import math
import os
import uuid

import pytest

from app.ai.rag.embedding_provider import (
    SentenceTransformerEmbeddingProvider,
    cosine_similarity,
)
from app.ai.rag.vector_store import ChromaVectorStore
from app.domain.interfaces.ai_providers import EmbeddedChunk

pytestmark = pytest.mark.embedding_integration

SMOKE_COLLECTION = "devguard_embedding_pytest_tmp"


@pytest.fixture(scope="session")
def st_provider() -> SentenceTransformerEmbeddingProvider:
    """Load the real MiniLM model once per test session."""
    return SentenceTransformerEmbeddingProvider(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        device="cpu",
        batch_size=8,
        normalize=True,
        max_input_characters=12_000,
        lazy_load=False,
    )


def _chroma_available() -> bool:
    host = os.environ.get("CHROMA_HOST", "localhost")
    port = int(os.environ.get("CHROMA_PORT", "8001"))
    try:
        store = ChromaVectorStore(
            host=host,
            port=port,
            collection_name=SMOKE_COLLECTION,
            connect_retries=1,
            connect_retry_delay_s=0.1,
        )
        return store.check_health().status != "unavailable"
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _chroma_available(), reason="Chroma service not reachable")
def test_real_embeddings_chroma_ranking(st_provider: SentenceTransformerEmbeddingProvider) -> None:
    assert st_provider.embedding_dimension == 384
    assert st_provider.selected_device == "cpu"
    assert st_provider.load_count == 1

    related_a = st_provider.embed_query("AWS AccessDenied during deployment")
    related_b = st_provider.embed_query("IAM permission denied when deploying to AWS")
    unrelated = st_provider.embed_query("Python assertion failed in unit test")
    assert cosine_similarity(related_a, related_b) > cosine_similarity(related_a, unrelated)

    host = os.environ.get("CHROMA_HOST", "localhost")
    port = int(os.environ.get("CHROMA_PORT", "8001"))
    identity = st_provider.config_identity()
    store = ChromaVectorStore(
        host=host,
        port=port,
        collection_name=SMOKE_COLLECTION,
        embedding_identity=identity,
        connect_retries=2,
    )
    with contextlib.suppress(Exception):
        store.delete_collection()

    store = ChromaVectorStore(
        host=host,
        port=port,
        collection_name=SMOKE_COLLECTION,
        embedding_identity=identity,
        connect_retries=2,
    )
    docs = [
        ("doc-aws", "AWS IAM AccessDenied permission failure during deployment"),
        ("doc-docker", "Docker COPY instruction failed because the source file is missing"),
        ("doc-terraform", "Terraform configuration references an undeclared resource"),
        ("doc-test", "Python unit test assertion failure"),
    ]
    chunks = [
        EmbeddedChunk(
            chunk_id=f"{doc_id}-{uuid.uuid4().hex[:8]}",
            text=text,
            metadata={"doc_id": doc_id},
        )
        for doc_id, text in docs
    ]
    vectors = st_provider.embed_documents([c.text for c in chunks])
    assert all(isinstance(v, list) and all(isinstance(x, float) for x in v) for v in vectors)
    store.upsert(chunks, vectors)

    cases = [
        ("permission denied while deploying to AWS", "doc-aws"),
        ("Docker build cannot find copied file", "doc-docker"),
        ("Terraform resource has not been declared", "doc-terraform"),
        ("pytest assertion error", "doc-test"),
    ]
    for query, expected in cases:
        hits = store.query(embedding=st_provider.embed_query(query), top_k=4)
        assert hits, f"no hits for {query}"
        assert hits[0].metadata.get("doc_id") == expected, (
            f"query={query!r} expected={expected} got={hits[0].metadata.get('doc_id')}"
        )

    store.delete_collection()
    # Confirm production knowledge collection name was not used.
    assert store.collection_name == SMOKE_COLLECTION


def test_real_model_normalisation_and_health(
    st_provider: SentenceTransformerEmbeddingProvider,
) -> None:
    vector = st_provider.embed_query("DevGuard AI embedding health check")
    mag = math.sqrt(sum(v * v for v in vector))
    assert mag == pytest.approx(1.0, abs=1e-3)
    health = st_provider.health_check()
    assert health.status == "healthy"
    assert health.dimension == 384
    assert health.external_cost == "not_applicable"
    assert st_provider.load_count == 1
