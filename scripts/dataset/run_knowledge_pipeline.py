#!/usr/bin/env python3
"""Phase 4–7 research knowledge pipeline.

4) Chunk curated (+ optional candidates) knowledge records
5) Embed with MiniLM and upsert into Chroma collection ``devguard_research_knowledge``
6) Evaluate retrieval (Precision@k / Recall@k / MRR / nDCG)
7) Grounded diagnosis CLI path (local reasoner default; OpenAI optional)

Does not modify the product collection ``devguard_knowledge`` unless explicitly overridden.

Usage (from repo root):

  # Host against Docker-published Chroma:
  export CHROMA_HOST=localhost CHROMA_PORT=8001
  export EMBEDDING_PROVIDER=sentence_transformers EMBEDDING_DEVICE=cpu

  python scripts/dataset/run_knowledge_pipeline.py
  python scripts/dataset/run_knowledge_pipeline.py --include-candidates
  python scripts/dataset/run_knowledge_pipeline.py --diagnose "AWS AccessDenied during deploy" --llm local
  python scripts/dataset/run_knowledge_pipeline.py --diagnose "..." --llm openai
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
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

from app.ai.rag.embedding_provider import (  # noqa: E402
    build_embedding_provider,
)
from app.ai.rag.vector_store import ChromaVectorStore  # noqa: E402
from app.domain.interfaces.ai_providers import EmbeddedChunk  # noqa: E402
from app.domain.services.secret_masker import mask_secrets  # noqa: E402
from chunk_utils import chunk_knowledge_record  # noqa: E402

CURATED_DIR = REPO_ROOT / "datasets" / "processed" / "knowledge" / "curated"
CANDIDATES_DIR = REPO_ROOT / "datasets" / "processed" / "knowledge" / "candidates"
CHUNKS_DIR = REPO_ROOT / "datasets" / "processed" / "chunks"
REPORTS_DIR = REPO_ROOT / "datasets" / "reports"
EVAL_QUERIES = REPO_ROOT / "datasets" / "manifests" / "retrieval_eval_queries.json"
VERSION_PATH = REPO_ROOT / "datasets" / "VERSION"

DEFAULT_COLLECTION = "devguard_research_knowledge"


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _load_json_dir(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return records


def _chroma_settings() -> tuple[str, int, str]:
    host = os.environ.get("CHROMA_HOST", "localhost").strip()
    # Compose service hostname is useless on the Mac host.
    if host in {"chroma", "devguard_chroma"}:
        host = "localhost"
    port = int(os.environ.get("CHROMA_PORT", "8001"))
    # Prefer published host port when using localhost.
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


def phase4_chunk(*, include_candidates: bool, max_chars: int = 900) -> dict[str, Any]:
    records = _load_json_dir(CURATED_DIR)
    source = "curated"
    if include_candidates:
        records.extend(_load_json_dir(CANDIDATES_DIR))
        source = "curated+candidates"

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    for old in CHUNKS_DIR.glob("*.json"):
        old.unlink()
    for old in CHUNKS_DIR.glob("*.jsonl"):
        old.unlink()

    all_chunks: list[dict[str, Any]] = []
    for record in records:
        chunks = chunk_knowledge_record(record, max_chars=max_chars)
        for chunk in chunks:
            path = CHUNKS_DIR / f"{chunk['chunk_id']}.json"
            path.write_text(json.dumps(chunk, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            all_chunks.append(chunk)

    manifest = CHUNKS_DIR / "chunks_manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as handle:
        for chunk in all_chunks:
            handle.write(
                json.dumps(
                    {
                        "chunk_id": chunk["chunk_id"],
                        "knowledge_id": chunk["knowledge_id"],
                        "failure_category": chunk["failure_category"],
                        "technology": chunk["technology"],
                        "char_count": chunk["char_count"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    return {
        "phase": 4,
        "source": source,
        "knowledge_records": len(records),
        "chunks": len(all_chunks),
        "output_dir": _rel(CHUNKS_DIR),
    }


def phase5_index(
    *,
    collection_name: str,
    recreate: bool,
    batch_size: int = 32,
) -> dict[str, Any]:
    chunks = []
    for path in sorted(CHUNKS_DIR.glob("*-c*.json")):
        chunks.append(json.loads(path.read_text(encoding="utf-8")))
    if not chunks:
        raise RuntimeError("No chunks found. Run phase 4 first.")

    provider = _embedding_provider()
    identity = None
    if hasattr(provider, "config_identity"):
        identity = provider.config_identity()

    host, port, persist = _chroma_settings()
    store = ChromaVectorStore(
        host=host,
        port=port,
        persist_path=persist,
        collection_name=collection_name,
        embedding_identity=identity,
        connect_retries=3,
    )
    if recreate:
        try:
            store.delete_collection()
        except Exception:  # noqa: BLE001
            pass
        store = ChromaVectorStore(
            host=host,
            port=port,
            persist_path=persist,
            collection_name=collection_name,
            embedding_identity=identity,
            connect_retries=3,
        )

    texts = [c["text"] for c in chunks]
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        vectors.extend(provider.embed_documents(batch))

    embedded = [
        EmbeddedChunk(
            chunk_id=c["chunk_id"],
            text=c["text"],
            metadata={
                "knowledge_id": c.get("knowledge_id") or "",
                "incident_id": c.get("incident_id") or "",
                "technology": c.get("technology") or "",
                "failure_category": c.get("failure_category") or "",
                "repository": c.get("repository") or "",
                "issue_url": c.get("issue_url") or "",
                "section": c.get("section") or "",
                "document_status": "active",
                "source_type": "research_knowledge",
            },
        )
        for c in chunks
    ]
    # Upsert in batches to keep payloads bounded.
    for start in range(0, len(embedded), batch_size):
        store.upsert(embedded[start : start + batch_size], vectors[start : start + batch_size])

    health = store.check_health()
    return {
        "phase": 5,
        "collection": collection_name,
        "host": host,
        "port": port,
        "chunks_indexed": len(chunks),
        "embedding_provider": getattr(provider, "provider_name", provider.name),
        "embedding_dimension": getattr(provider, "embedding_dimension", None),
        "chroma_status": health.status,
        "collection_count": health.collection_count,
        "recreate": recreate,
    }


def _dcg(relevances: list[float]) -> float:
    total = 0.0
    for idx, rel in enumerate(relevances):
        total += (2**rel - 1) / math.log2(idx + 2)
    return total


def _ndcg(relevances: list[float], ideal: list[float]) -> float:
    denom = _dcg(sorted(ideal, reverse=True)[: len(relevances)])
    if denom <= 0:
        return 0.0
    return _dcg(relevances) / denom


def _default_eval_queries() -> list[dict[str, Any]]:
    return [
        {
            "query_id": "q-aws-iam",
            "query_text": "AWS AccessDenied permission denied during deployment",
            "expected_failure_category": "aws_permission_failure",
            "expected_technology": "aws",
        },
        {
            "query_id": "q-docker-copy",
            "query_text": "Docker COPY failed because source file is missing",
            "expected_failure_category": "docker_failure",
            "expected_technology": "docker",
        },
        {
            "query_id": "q-terraform-undeclared",
            "query_text": "Terraform undeclared resource reference failure",
            "expected_failure_category": "terraform_failure",
            "expected_technology": "terraform",
        },
        {
            "query_id": "q-actions-runner",
            "query_text": "GitHub Actions runner workflow configuration failure",
            "expected_failure_category": "configuration_failure",
            "expected_technology": "github_actions",
        },
        {
            "query_id": "q-k8s-deploy",
            "query_text": "Kubernetes deployment CrashLoopBackOff or ImagePullBackOff",
            "expected_failure_category": "deployment_failure",
            "expected_technology": "kubernetes",
        },
        {
            "query_id": "q-node-deps",
            "query_text": "npm dependency conflict ModuleNotFoundError in CI",
            "expected_failure_category": "dependency_failure",
            "expected_technology": "node",
        },
        {
            "query_id": "q-java-build",
            "query_text": "Maven or Gradle build failed in GitHub Actions",
            "expected_failure_category": "build_failure",
            "expected_technology": "java",
        },
        {
            "query_id": "q-network-timeout",
            "query_text": "connection timeout DNS resolution failure in pipeline",
            "expected_failure_category": "network_failure",
            "expected_technology": None,
        },
    ]


def _relevance_grade(hit_meta: dict[str, Any], query: dict[str, Any]) -> int:
    cat = str(hit_meta.get("failure_category") or "")
    tech = str(hit_meta.get("technology") or "")
    expected_cat = query.get("expected_failure_category")
    expected_tech = query.get("expected_technology")
    if expected_cat and cat == expected_cat and expected_tech and tech == expected_tech:
        return 3
    if expected_cat and cat == expected_cat:
        return 2
    if expected_tech and tech == expected_tech:
        return 1
    return 0


def phase6_evaluate(*, collection_name: str, top_k: int = 5) -> dict[str, Any]:
    if EVAL_QUERIES.exists():
        payload = json.loads(EVAL_QUERIES.read_text(encoding="utf-8"))
        queries = payload.get("queries") or _default_eval_queries()
    else:
        queries = _default_eval_queries()
        EVAL_QUERIES.parent.mkdir(parents=True, exist_ok=True)
        EVAL_QUERIES.write_text(
            json.dumps({"queries": queries, "relevance": "category_technology_heuristic"}, indent=2)
            + "\n",
            encoding="utf-8",
        )

    provider = _embedding_provider()
    host, port, persist = _chroma_settings()
    store = ChromaVectorStore(
        host=host,
        port=port,
        persist_path=persist,
        collection_name=collection_name,
        connect_retries=3,
    )

    per_query: list[dict[str, Any]] = []
    precision_scores: list[float] = []
    recall_scores: list[float] = []
    mrr_scores: list[float] = []
    ndcg_scores: list[float] = []

    # Approximate gold set size per category from indexed chunks.
    chunks = [json.loads(p.read_text(encoding="utf-8")) for p in CHUNKS_DIR.glob("*-c*.json")]
    cat_counts: Counter[str] = Counter(
        str(c.get("failure_category") or "") for c in chunks if c.get("failure_category")
    )

    for query in queries:
        qtext, _ = mask_secrets(str(query["query_text"]))
        embedding = provider.embed_query(qtext)
        hits = store.query(embedding=embedding, top_k=top_k)
        grades = [_relevance_grade(hit.metadata, query) for hit in hits]
        relevant_flags = [1 if g >= 2 else 0 for g in grades]
        precision = sum(relevant_flags) / max(1, len(relevant_flags))
        expected_cat = str(query.get("expected_failure_category") or "")
        gold_n = max(1, min(top_k, cat_counts.get(expected_cat, top_k)))
        recall = sum(relevant_flags) / gold_n
        rr = 0.0
        for idx, flag in enumerate(relevant_flags, start=1):
            if flag:
                rr = 1.0 / idx
                break
        ndcg = _ndcg([float(g) for g in grades], [3.0] * top_k)

        precision_scores.append(precision)
        recall_scores.append(min(1.0, recall))
        mrr_scores.append(rr)
        ndcg_scores.append(ndcg)
        per_query.append(
            {
                "query_id": query.get("query_id"),
                "query_text": query.get("query_text"),
                "precision_at_k": round(precision, 4),
                "recall_at_k_approx": round(min(1.0, recall), 4),
                "mrr": round(rr, 4),
                "ndcg": round(ndcg, 4),
                "top_hits": [
                    {
                        "chunk_id": hit.chunk_id,
                        "score": round(hit.score, 4),
                        "failure_category": hit.metadata.get("failure_category"),
                        "technology": hit.metadata.get("technology"),
                        "grade": grade,
                        "title_hint": hit.text.splitlines()[0][:120] if hit.text else "",
                    }
                    for hit, grade in zip(hits, grades, strict=False)
                ],
            }
        )

    def avg(values: list[float]) -> float:
        return round(sum(values) / max(1, len(values)), 4)

    return {
        "phase": 6,
        "collection": collection_name,
        "k": top_k,
        "queries": len(queries),
        "metrics": {
            "precision_at_k": avg(precision_scores),
            "recall_at_k_approx": avg(recall_scores),
            "mrr": avg(mrr_scores),
            "ndcg": avg(ndcg_scores),
        },
        "per_query": per_query,
        "notes": [
            "Relevance is heuristic (category/technology match) unless human graded labels are added.",
            "Recall uses an approximate gold size from indexed chunk category counts.",
        ],
    }


async def phase7_diagnose(
    *,
    query: str,
    collection_name: str,
    llm: str,
    top_k: int = 5,
) -> dict[str, Any]:
    from app.ai.reasoning.reasoning_provider import build_reasoning_provider
    from app.domain.interfaces.ai_providers import RecommendationRequest, RootCauseRequest

    masked_query, _ = mask_secrets(query)
    provider = _embedding_provider()
    host, port, persist = _chroma_settings()
    store = ChromaVectorStore(
        host=host,
        port=port,
        persist_path=persist,
        collection_name=collection_name,
        connect_retries=3,
    )
    embedding = provider.embed_query(masked_query)
    hits = store.query(embedding=embedding, top_k=top_k)
    retrieved_docs = [
        {
            "chunk_id": hit.chunk_id,
            "content": hit.text[:1200],
            "score": hit.score,
            "metadata": hit.metadata,
        }
        for hit in hits
    ]

    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    if llm == "openai":
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY required for --llm openai")
        reasoner = build_reasoning_provider("openai", api_key=api_key, model=model)
    else:
        reasoner = build_reasoning_provider("local")

    # Lightweight category guess from top hit.
    top_cat = str((hits[0].metadata.get("failure_category") if hits else "") or "unknown_failure")
    root_req = RootCauseRequest(
        classification_category=top_cat,
        classification_confidence=0.7 if hits else 0.4,
        root_cause_summary=f"Likely {top_cat.replace('_', ' ')} based on retrieved incidents.",
        technical_explanation=masked_query[:800],
        evidence=[{"id": "q1", "summary": masked_query[:300]}],
        retrieved_docs=retrieved_docs,
        signals={"query": masked_query[:200]},
        safety_rules=["Do not invent secrets", "Ground claims in retrieved docs"],
    )
    root = await reasoner.generate_root_cause(root_req)
    recs = await reasoner.generate_recommendations(
        RecommendationRequest(
            root_cause=root,
            evidence=[{"id": "q1", "summary": masked_query[:300]}],
            retrieved_docs=retrieved_docs,
            template_steps=[
                {
                    "order": 1,
                    "action": "Review retrieved incident evidence",
                    "explanation": "Compare symptoms with top retrieved knowledge chunks.",
                },
                {
                    "order": 2,
                    "action": "Validate fix in a non-production environment",
                    "explanation": "Apply the closest matching resolution carefully.",
                },
            ],
        )
    )
    return {
        "phase": 7,
        "llm_provider": reasoner.name,
        "query_masked": masked_query,
        "retrieved": retrieved_docs,
        "root_cause": root,
        "recommendations": recs,
        "external_api_used": llm == "openai",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-candidates", action="store_true")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument(
        "--recreate-collection",
        action="store_true",
        help="Delete/recreate the research collection before indexing",
    )
    parser.add_argument("--skip-index", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--diagnose", default=None, help="Run Phase 7 diagnosis for this query")
    parser.add_argument("--llm", choices=["local", "openai"], default="local")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args(argv)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_version": "0.4.0-phases4-7",
    }

    print("=== Phase 4: chunk ===")
    report["phase4"] = phase4_chunk(include_candidates=args.include_candidates)
    print(json.dumps(report["phase4"], indent=2))

    if not args.skip_index:
        print("=== Phase 5: embed + Chroma ===")
        # Default recreate for research collection to avoid dimension/identity clashes.
        recreate = args.recreate_collection or True
        report["phase5"] = phase5_index(
            collection_name=args.collection,
            recreate=recreate,
        )
        print(json.dumps(report["phase5"], indent=2))
    else:
        report["phase5"] = {"skipped": True}

    if not args.skip_eval:
        print("=== Phase 6: retrieval evaluation ===")
        report["phase6"] = phase6_evaluate(collection_name=args.collection, top_k=args.top_k)
        print(json.dumps({"metrics": report["phase6"]["metrics"], "queries": report["phase6"]["queries"]}, indent=2))
    else:
        report["phase6"] = {"skipped": True}

    if args.diagnose:
        print("=== Phase 7: grounded diagnosis ===")
        report["phase7"] = asyncio.run(
            phase7_diagnose(
                query=args.diagnose,
                collection_name=args.collection,
                llm=args.llm,
                top_k=args.top_k,
            )
        )
        # Safe print summary (no secrets).
        print(
            json.dumps(
                {
                    "llm_provider": report["phase7"]["llm_provider"],
                    "external_api_used": report["phase7"]["external_api_used"],
                    "retrieved_count": len(report["phase7"]["retrieved"]),
                    "root_cause_summary": (report["phase7"]["root_cause"] or {}).get("summary"),
                    "top_chunk_ids": [d["chunk_id"] for d in report["phase7"]["retrieved"][:3]],
                },
                indent=2,
            )
        )
    else:
        # Still demonstrate local diagnosis once with a safe default query.
        print("=== Phase 7: grounded diagnosis (default local sample) ===")
        report["phase7"] = asyncio.run(
            phase7_diagnose(
                query="AWS AccessDenied during deployment IAM permission failure",
                collection_name=args.collection,
                llm=args.llm,
                top_k=args.top_k,
            )
        )
        print(
            json.dumps(
                {
                    "llm_provider": report["phase7"]["llm_provider"],
                    "external_api_used": report["phase7"]["external_api_used"],
                    "retrieved_count": len(report["phase7"]["retrieved"]),
                    "root_cause_summary": (report["phase7"]["root_cause"] or {}).get("summary"),
                },
                indent=2,
            )
        )

    report_path = REPORTS_DIR / "phases4_7_pipeline_report.json"
    # Avoid storing full retrieved texts twice in the archived report if huge.
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    VERSION_PATH.write_text("0.4.0-phases4-7\n", encoding="utf-8")
    print(f"report={_rel(report_path)}")
    print("STATUS: phases 4–7 complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
