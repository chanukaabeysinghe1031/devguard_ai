#!/usr/bin/env python3
"""Official documentation enrichment pipeline for the research corpus.

Parse → mask → metadata → chunk (shared chunker) → dedupe → embed (MiniLM) →
upsert into ``devguard_research_knowledge`` (never recreate; never touch product
``devguard_knowledge``) → hybrid retrieval verification → report + version bump.

Usage (repo root):

  export CHROMA_HOST=localhost CHROMA_PORT=8001
  export EMBEDDING_PROVIDER=sentence_transformers EMBEDDING_DEVICE=cpu

  backend/.venv/bin/python scripts/dataset/download_official_docs.py
  backend/.venv/bin/python scripts/dataset/run_official_docs_pipeline.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (BACKEND_ROOT, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.ai.rag.embedding_provider import build_embedding_provider  # noqa: E402
from app.ai.rag.vector_store import ChromaVectorStore  # noqa: E402
from app.domain.interfaces.ai_providers import EmbeddedChunk  # noqa: E402
from app.domain.services.secret_masker import mask_secrets  # noqa: E402
from chunk_utils import chunk_official_document  # noqa: E402
from download_official_docs import VENDOR_DIRS  # noqa: E402
from official_docs_duplicates import DuplicateTracker  # noqa: E402
from official_docs_metadata import (  # noqa: E402
    build_document_record,
    chroma_metadata_from_chunk,
)
from official_docs_parser import html_to_markdown  # noqa: E402

DOCS_ROOT = REPO_ROOT / "datasets" / "raw" / "docs"
PARSED_DIR = REPO_ROOT / "datasets" / "processed" / "docs" / "parsed"
CHUNKS_DIR = REPO_ROOT / "datasets" / "processed" / "docs" / "chunks"
REPORTS_DIR = REPO_ROOT / "datasets" / "reports"
VERSION_PATH = REPO_ROOT / "datasets" / "VERSION"
CORPUS_VERSION = "0.5.0-official-docs"
DEFAULT_COLLECTION = "devguard_research_knowledge"
PRODUCT_COLLECTION = "devguard_knowledge"

VERIFY_QUERIES = [
    {
        "query_id": "v-aws",
        "query_text": "AWS AccessDenied during deployment",
        "expect_tech": "aws",
        "expect_doc_vendor_substrings": ["aws"],
    },
    {
        "query_id": "v-terraform",
        "query_text": "Terraform undeclared resource",
        "expect_tech": "terraform",
        "expect_doc_vendor_substrings": ["terraform"],
    },
    {
        "query_id": "v-docker",
        "query_text": "Docker COPY failed",
        "expect_tech": "docker",
        "expect_doc_vendor_substrings": ["docker"],
    },
]


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _chroma_settings() -> tuple[str, int, str]:
    host = os.environ.get("CHROMA_HOST", "localhost").strip()
    if host in {"chroma", "devguard_chroma"}:
        host = "localhost"
    port = int(os.environ.get("CHROMA_PORT", "8001"))
    if host in {"localhost", "127.0.0.1"} and port == 8000:
        port = 8001
    persist = os.environ.get("CHROMA_PERSIST_PATH", "./storage/chroma")
    return host, port, persist


def _embedding_provider() -> Any:
    provider = os.environ.get("EMBEDDING_PROVIDER", "sentence_transformers")
    model = os.environ.get(
        "EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )
    device = os.environ.get("EMBEDDING_DEVICE", "cpu")
    batch_size = int(os.environ.get("EMBEDDING_BATCH_SIZE", "16"))
    normalize = os.environ.get("EMBEDDING_NORMALIZE", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return build_embedding_provider(
        provider,
        model=model,
        device=device,  # type: ignore[arg-type]
        batch_size=batch_size,
        normalize=normalize,
        lazy_load=True,
    )


def _load_sources(vendors: list[str]) -> list[tuple[str, dict[str, Any]]]:
    items: list[tuple[str, dict[str, Any]]] = []
    for vendor in vendors:
        path = DOCS_ROOT / vendor / "source_list.json"
        for source in json.loads(path.read_text(encoding="utf-8")):
            items.append((vendor, source))
    return items


def parse_documents(*, vendors: list[str]) -> dict[str, Any]:
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    parsed_docs: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for vendor, source in _load_sources(vendors):
        document_id = source["document_id"]
        html_path = DOCS_ROOT / vendor / "downloads" / f"{document_id}.html"
        if not html_path.exists():
            failures.append({"document_id": document_id, "error": "missing download"})
            continue
        html = html_path.read_text(encoding="utf-8", errors="replace")
        parsed = html_to_markdown(html)
        markdown = parsed.get("markdown") or ""
        if len(markdown.strip()) < 80:
            failures.append({"document_id": document_id, "error": "parsed content too short"})
            continue
        masked, _count = mask_secrets(markdown)
        download_meta = {}
        dm_path = DOCS_ROOT / vendor / "download_manifest.json"
        if dm_path.exists():
            for entry in json.loads(dm_path.read_text(encoding="utf-8")):
                if entry.get("document_id") == document_id:
                    download_meta = entry
                    break
        record = build_document_record(
            source=source,
            markdown=masked,
            retrieved_at=download_meta.get("retrieved"),
            title_override=parsed.get("title") or source.get("title"),
            headings=parsed.get("headings") or [],
        )
        out = PARSED_DIR / f"{document_id}.json"
        _write_json(out, record)
        parsed_docs.append(record)

    return {
        "documents_parsed": len(parsed_docs),
        "failures": failures,
        "documents": parsed_docs,
    }


def chunk_documents(
    documents: list[dict[str, Any]],
    *,
    max_chars: int = 900,
    overlap: int = 100,
) -> dict[str, Any]:
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    for old in CHUNKS_DIR.glob("*.json"):
        old.unlink()

    all_chunks: list[dict[str, Any]] = []
    for document in documents:
        chunks = chunk_official_document(document, max_chars=max_chars, overlap=overlap)
        for chunk in chunks:
            path = CHUNKS_DIR / f"{chunk['chunk_id']}.json"
            _write_json(path, chunk)
            all_chunks.append(chunk)

    avg = (
        round(sum(c["char_count"] for c in all_chunks) / len(all_chunks), 1) if all_chunks else 0.0
    )
    return {
        "chunks_created": len(all_chunks),
        "average_chunk_size": avg,
        "chunks": all_chunks,
    }


def _existing_collection_state(store: ChromaVectorStore) -> tuple[set[str], list[dict[str, Any]]]:
    collection = getattr(store, "_collection", None) or store._get_existing_collection()  # noqa: SLF001
    if collection is None:
        return set(), []
    store._collection = collection  # noqa: SLF001
    try:
        result = collection.get(include=["metadatas"])
        ids = [str(i) for i in (result.get("ids") or [])]
        metas = result.get("metadatas") or []
        prior: list[dict[str, Any]] = []
        for chunk_id, meta in zip(ids, metas, strict=False):
            row = dict(meta or {})
            row["chunk_id"] = chunk_id
            prior.append(row)
        return set(ids), prior
    except Exception:  # noqa: BLE001
        return set(), []


def index_chunks(
    chunks: list[dict[str, Any]],
    *,
    collection_name: str,
    batch_size: int = 16,
) -> dict[str, Any]:
    if collection_name == PRODUCT_COLLECTION:
        raise RuntimeError("Refusing to modify product collection devguard_knowledge")

    provider = _embedding_provider()
    identity = provider.config_identity() if hasattr(provider, "config_identity") else None
    host, port, persist = _chroma_settings()
    store = ChromaVectorStore(
        host=host,
        port=port,
        persist_path=persist,
        collection_name=collection_name,
        embedding_identity=identity,
        connect_retries=3,
    )

    existing_ids, prior_meta = _existing_collection_state(store)
    tracker = DuplicateTracker()
    tracker.register_existing(prior_meta)

    to_embed: list[dict[str, Any]] = []
    decisions: Counter[str] = Counter()
    for chunk in chunks:
        decision = tracker.classify_chunk(chunk, existing_ids=existing_ids)
        decisions[decision] += 1
        if decision in {"index", "update"}:
            to_embed.append(chunk)

    vectors: list[list[float]] = []
    if to_embed:
        texts = [c["text"] for c in to_embed]
        for start in range(0, len(texts), batch_size):
            vectors.extend(provider.embed_documents(texts[start : start + batch_size]))

        embedded = [
            EmbeddedChunk(
                chunk_id=c["chunk_id"],
                text=c["text"],
                metadata=chroma_metadata_from_chunk(c),
            )
            for c in to_embed
        ]
        for start in range(0, len(embedded), batch_size):
            store.upsert(
                embedded[start : start + batch_size],
                vectors[start : start + batch_size],
            )

    health = store.check_health()
    return {
        "collection": collection_name,
        "host": host,
        "port": port,
        "chunks_considered": len(chunks),
        "chunks_indexed": decisions.get("index", 0),
        "chunks_updated": decisions.get("update", 0),
        "chunks_skipped": decisions.get("skip", 0),
        "chunks_rejected": decisions.get("reject", 0),
        "embedding_provider": getattr(provider, "provider_name", provider.name),
        "embedding_dimension": getattr(provider, "embedding_dimension", None),
        "embedding_model": getattr(provider, "model_name", None)
        or (identity or {}).get("devguard_embedding_model"),
        "chroma_status": health.status,
        "collection_count": health.collection_count,
        "duplicate_summary": tracker.summary(),
        "product_collection_untouched": PRODUCT_COLLECTION,
    }


def verify_retrieval(*, collection_name: str, top_k: int = 25) -> dict[str, Any]:
    provider = _embedding_provider()
    identity = provider.config_identity() if hasattr(provider, "config_identity") else None
    host, port, persist = _chroma_settings()
    store = ChromaVectorStore(
        host=host,
        port=port,
        persist_path=persist,
        collection_name=collection_name,
        embedding_identity=identity,
        connect_retries=3,
    )

    results: list[dict[str, Any]] = []
    for query in VERIFY_QUERIES:
        masked_q, _ = mask_secrets(query["query_text"])
        embedding = provider.embed_query(masked_q)
        hits = store.query(embedding=embedding, top_k=top_k)
        top = [
            {
                "chunk_id": h.chunk_id,
                "score": round(float(h.score), 4),
                "source_type": (h.metadata or {}).get("source_type"),
                "vendor": (h.metadata or {}).get("vendor"),
                "technology": (h.metadata or {}).get("technology"),
                "section": (h.metadata or {}).get("section"),
            }
            for h in hits
        ]
        has_github = any(
            (t.get("source_type") in {"research_knowledge", "public_github_issue"})
            or str(t.get("chunk_id", "")).startswith("kn-gh-")
            for t in top
        )
        expect_tech = query["expect_tech"]
        has_docs = any(
            t.get("source_type") == "official_documentation"
            and (
                str(t.get("technology") or "").lower() == expect_tech
                or any(
                    s in str(t.get("vendor") or "").lower()
                    for s in query["expect_doc_vendor_substrings"]
                )
            )
            for t in top
        )
        first_github = next(
            (
                t
                for t in top
                if (t.get("source_type") in {"research_knowledge", "public_github_issue"})
                or str(t.get("chunk_id", "")).startswith("kn-gh-")
            ),
            None,
        )
        first_doc = next(
            (t for t in top if t.get("source_type") == "official_documentation"),
            None,
        )
        results.append(
            {
                "query_id": query["query_id"],
                "query_text": query["query_text"],
                "top_k": top_k,
                "passed": bool(has_github and has_docs),
                "has_github_incidents": has_github,
                "has_official_docs": has_docs,
                "first_github_hit": first_github,
                "first_official_doc_hit": first_doc,
                "top_results": top[:10],
            }
        )

    return {
        "queries": results,
        "all_passed": all(r["passed"] for r in results),
    }


def build_report(
    *,
    parse_result: dict[str, Any],
    chunk_result: dict[str, Any],
    index_result: dict[str, Any],
    verify_result: dict[str, Any],
    vendors: list[str],
) -> dict[str, Any]:
    documents = parse_result.get("documents") or []
    chunks = chunk_result.get("chunks") or []
    vendor_counts = Counter(str(d.get("vendor")) for d in documents)
    category_counts = Counter(str(d.get("category")) for d in documents)
    tech_counts = Counter(str(d.get("technology")) for d in documents)
    coverage: dict[str, bool] = {}
    for vendor_dir in vendors:
        sources = json.loads((DOCS_ROOT / vendor_dir / "source_list.json").read_text(encoding="utf-8"))
        ids = {s["document_id"] for s in sources}
        coverage[vendor_dir] = any(d.get("document_id") in ids for d in documents)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "corpus_version": CORPUS_VERSION,
        "creation_date": datetime.now(UTC).date().isoformat(),
        "document_count": len(documents),
        "documents_downloaded": sum(
            1
            for vendor_dir in vendors
            for _ in (DOCS_ROOT / vendor_dir).glob("downloads/*.html")
        ),
        "documents_parsed": len(documents),
        "chunk_count": len(chunks),
        "chunks_created": len(chunks),
        "chunks_indexed": len(chunks),
        "chunks_indexed_this_run": int(index_result.get("chunks_indexed", 0))
        + int(index_result.get("chunks_updated", 0)),
        "duplicate_count": index_result.get("chunks_skipped", 0),
        "vendors": dict(vendor_counts),
        "categories": dict(category_counts),
        "technologies": dict(tech_counts),
        "average_chunk_size": chunk_result.get("average_chunk_size"),
        "coverage": coverage,
        "embedding_model": index_result.get("embedding_model")
        or "sentence-transformers/all-MiniLM-L6-v2",
        "embedding_dimension": index_result.get("embedding_dimension") or 384,
        "collection": index_result.get("collection"),
        "collection_count": index_result.get("collection_count"),
        "parse_failures": parse_result.get("failures") or [],
        "index": {
            k: index_result.get(k)
            for k in (
                "chunks_indexed",
                "chunks_updated",
                "chunks_skipped",
                "chunks_rejected",
                "chroma_status",
                "product_collection_untouched",
            )
        },
        "retrieval_verification": verify_result,
        "migration_created": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vendor", action="append", choices=list(VENDOR_DIRS))
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--max-chars", type=int, default=900)
    parser.add_argument("--overlap", type=int, default=100)
    parser.add_argument("--skip-index", action="store_true")
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args(argv)

    if args.collection == PRODUCT_COLLECTION:
        raise SystemExit("Refusing to use product collection devguard_knowledge")

    vendors = args.vendor or list(VENDOR_DIRS)
    parse_result = parse_documents(vendors=vendors)
    chunk_result = chunk_documents(
        parse_result["documents"],
        max_chars=args.max_chars,
        overlap=args.overlap,
    )

    if args.skip_index:
        index_result = {
            "collection": args.collection,
            "chunks_indexed": 0,
            "chunks_updated": 0,
            "chunks_skipped": 0,
            "chunks_rejected": 0,
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "embedding_dimension": 384,
            "product_collection_untouched": PRODUCT_COLLECTION,
        }
        verify_result = {"queries": [], "all_passed": False, "skipped": True}
    else:
        index_result = index_chunks(
            chunk_result["chunks"],
            collection_name=args.collection,
            batch_size=16,
        )
        verify_result = (
            {"queries": [], "all_passed": False, "skipped": True}
            if args.skip_verify
            else verify_retrieval(collection_name=args.collection)
        )

    report = build_report(
        parse_result=parse_result,
        chunk_result=chunk_result,
        index_result=index_result,
        verify_result=verify_result,
        vendors=vendors,
    )
    report_path = REPORTS_DIR / "official_docs_report.json"
    _write_json(report_path, report)
    VERSION_PATH.write_text(CORPUS_VERSION + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "corpus_version": CORPUS_VERSION,
                "documents_parsed": report["document_count"],
                "chunks_created": report["chunk_count"],
                "chunks_indexed": report["chunks_indexed"],
                "duplicates_skipped": report["duplicate_count"],
                "retrieval_all_passed": verify_result.get("all_passed"),
                "report": _rel(report_path),
            },
            indent=2,
        )
    )
    if not args.skip_index and not args.skip_verify and not verify_result.get("all_passed"):
        return 2
    if parse_result["documents_parsed"] == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
