"""Smoke-test embeddings and optional temporary Chroma retrieval."""

from __future__ import annotations

import argparse
import contextlib
import sys
import time
import uuid

from app.ai.rag.embedding_provider import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    build_embedding_provider,
    cosine_similarity,
)
from app.ai.rag.vector_store import ChromaVectorStore
from app.core.config import get_settings
from app.domain.interfaces.ai_providers import EmbeddedChunk

SMOKE_COLLECTION = "devguard_embedding_smoke_test"

SMOKE_DOCS = [
    ("doc-aws", "AWS IAM AccessDenied permission failure"),
    ("doc-docker", "Docker COPY failed because source file is missing"),
    ("doc-terraform", "Terraform reference to undeclared resource"),
]

SMOKE_QUERY = "AWS permission denied during deployment"
EXPECTED_TOP = "doc-aws"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Test DevGuard embedding provider")
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--device", default=None)
    parser.add_argument("--text", default="AWS AccessDenied during deployment")
    parser.add_argument(
        "--compare-text",
        default="IAM permission denied while deploying",
    )
    parser.add_argument("--with-chroma", action="store_true")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print first 5 embedding values (development only)",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    provider_name = args.provider or settings.embedding_provider
    model = args.model or settings.embedding_model
    device = args.device or settings.embedding_device

    try:
        provider = build_embedding_provider(
            provider_name,
            model=model,
            device=device,  # type: ignore[arg-type]
            batch_size=settings.embedding_batch_size,
            normalize=settings.embedding_normalize,
            max_input_characters=settings.embedding_max_input_characters,
        )
    except (EmbeddingConfigurationError, EmbeddingProviderError) as exc:
        print(f"Provider construction failed: {exc}")
        return 1

    t0 = time.perf_counter()
    first = provider.embed_query(args.text)
    first_ms = (time.perf_counter() - t0) * 1000.0
    t1 = time.perf_counter()
    second = provider.embed_query(args.compare_text)
    second_ms = (time.perf_counter() - t1) * 1000.0
    similarity = cosine_similarity(first, second)

    meta = provider.metadata() if hasattr(provider, "metadata") else {}
    print(f"provider: {meta.get('provider_name', provider.name)}")
    print(f"model: {meta.get('model_name', getattr(provider, 'model_name', provider.name))}")
    print(f"device: {meta.get('selected_device')}")
    print(f"dimension: {len(first)}")
    print(f"normalised: {meta.get('normalisation_enabled')}")
    print(f"first_embedding_latency_ms: {first_ms:.1f}")
    print(f"second_embedding_latency_ms: {second_ms:.1f}")
    print(f"cosine_similarity: {similarity:.4f}")
    if args.verbose:
        print(f"first_values_sample: {first[:5]}")

    if not args.with_chroma:
        return 0

    identity = provider.config_identity() if hasattr(provider, "config_identity") else None
    store = ChromaVectorStore(
        host=settings.chroma_host,
        port=settings.chroma_port,
        persist_path=settings.chroma_persist_path,
        collection_name=SMOKE_COLLECTION,
        tenant=settings.chroma_tenant,
        database=settings.chroma_database,
        embedding_identity=identity,
        connect_retries=3,
    )
    health = store.check_health()
    print(f"chroma_status: {health.status}")
    print(f"chroma_detail: {health.detail}")
    if health.status == "unavailable":
        return 1

    # Ensure a clean temporary collection for this run.
    with contextlib.suppress(Exception):
        store.delete_collection()

    # Rebuild store handle after delete so collection is recreated on upsert.
    store = ChromaVectorStore(
        host=settings.chroma_host,
        port=settings.chroma_port,
        persist_path=settings.chroma_persist_path,
        collection_name=SMOKE_COLLECTION,
        tenant=settings.chroma_tenant,
        database=settings.chroma_database,
        embedding_identity=identity,
        connect_retries=3,
    )

    chunks = [
        EmbeddedChunk(
            chunk_id=f"{doc_id}-{uuid.uuid4().hex[:8]}",
            text=text,
            metadata={"doc_id": doc_id},
        )
        for doc_id, text in SMOKE_DOCS
    ]
    vectors = provider.embed_documents([c.text for c in chunks])
    store.upsert(chunks, vectors)
    query_vec = provider.embed_query(SMOKE_QUERY)
    hits = store.query(embedding=query_vec, top_k=3)
    top_doc = hits[0].metadata.get("doc_id") if hits else None
    print(f"temporary_collection: {SMOKE_COLLECTION}")
    print(f"documents_indexed: {len(chunks)}")
    print(f"top_result_doc_id: {top_doc}")
    print(f"top_result_text: {hits[0].text if hits else None}")

    removed = False
    try:
        store.delete_collection()
        removed = True
    except Exception as exc:  # noqa: BLE001
        print(f"temporary_collection_cleanup_error: {type(exc).__name__}")
    print(f"temporary_collection_removed: {removed}")

    if top_doc != EXPECTED_TOP:
        print(f"verification_failed: expected {EXPECTED_TOP}, got {top_doc}")
        return 1
    if not removed:
        return 1
    print("verification: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
