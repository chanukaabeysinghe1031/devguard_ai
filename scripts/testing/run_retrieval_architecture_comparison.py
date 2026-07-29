#!/usr/bin/env python3
"""Compare primary-only vs federated (primary + secondary) retrieval.

Uses the human-gold benchmark labels. Mode A queries the labeled research
collection only. Mode B merges research (primary for this experiment) with the
product knowledge collection, then dedupes by chunk_id.

Does not alter gold labels.
"""

from __future__ import annotations

import csv
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(os.environ.get("DEVGUARD_REPO_ROOT", "")).resolve() if os.environ.get("DEVGUARD_REPO_ROOT") else Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
BENCH_SCRIPTS = REPO / "scripts" / "dataset" / "benchmark"
for path in (BACKEND, BENCH_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.ai.rag.embedding_provider import build_embedding_provider  # noqa: E402
from app.ai.rag.vector_store import ChromaVectorStore  # noqa: E402
from app.domain.services.secret_masker import mask_secrets  # noqa: E402
from metrics import (  # noqa: E402
    average_precision,
    hit_rate,
    mean,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

BENCH = REPO / "datasets" / "benchmark"
OUT = BENCH / "results" / "retrieval_architecture_comparison"

# Ten required smoke queries map onto category groups; full gold set is also evaluated.
REQUIRED_TECH_MARKERS = (
    "aws",
    "terraform",
    "docker",
    "github",
    "kubernetes",
    "npm",
    "maven",
    "python",
    "dns",
    "auth",
)

PRIMARY_COLLECTION = os.environ.get(
    "COMPARISON_PRIMARY_COLLECTION", "devguard_research_knowledge"
)
SECONDARY_COLLECTION = os.environ.get(
    "COMPARISON_SECONDARY_COLLECTION", "devguard_product_minilm"
)
TOP_K = int(os.environ.get("COMPARISON_TOP_K", "10"))


def _chroma() -> tuple[str, int, str]:
    host = os.environ.get("CHROMA_HOST", "chroma").strip()
    port = int(os.environ.get("CHROMA_PORT", "8000"))
    persist = os.environ.get("CHROMA_PERSIST_PATH", "./storage/chroma")
    return host, port, persist


def _load_gold() -> tuple[list[dict[str, str]], dict[str, dict[str, int]]]:
    queries = list(csv.DictReader((BENCH / "queries.csv").open(encoding="utf-8")))
    gold: dict[str, dict[str, int]] = defaultdict(dict)
    with (BENCH / "gold_labels.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            qid = row.get("query_id") or ""
            doc = row.get("document_id") or ""
            if qid and doc:
                gold[qid][doc] = int(row.get("relevance") or 0)
    return queries, dict(gold)


def _query_store(store: ChromaVectorStore, embedding: list[float], top_k: int) -> list[Any]:
    try:
        return store.query(
            embedding=embedding,
            top_k=top_k,
            where={"document_status": {"$eq": "active"}},
        )
    except Exception:
        return store.query(embedding=embedding, top_k=top_k)


def _merge_hits(primary_hits: list[Any], secondary_hits: list[Any], top_k: int) -> list[Any]:
    merged: dict[str, Any] = {}
    for hit in list(primary_hits) + list(secondary_hits):
        prev = merged.get(hit.chunk_id)
        if prev is None or float(hit.score) > float(prev.score):
            merged[hit.chunk_id] = hit
    return sorted(merged.values(), key=lambda h: float(h.score), reverse=True)[:top_k]


def _source_bucket(meta: dict[str, Any] | None) -> str:
    meta = meta or {}
    source = str(meta.get("source_type") or meta.get("corpus") or meta.get("vendor") or "").lower()
    title = str(meta.get("title") or "").lower()
    text_hint = f"{source} {title}"
    if "official" in text_hint or "docs" in text_hint or "documentation" in text_hint:
        return "official_docs"
    if "github" in text_hint or str(meta.get("chunk_id", "")).startswith("kn-gh"):
        return "github_incident"
    if "product" in text_hint or "knowledge_base" in text_hint:
        return "product_knowledge"
    if source:
        return source
    return "unknown"


def _metrics_for_hits(hits: list[Any], grades: dict[str, int]) -> dict[str, float]:
    retrieved_ids = [h.chunk_id for h in hits]
    retrieved_grades = [float(grades.get(doc, 0)) for doc in retrieved_ids]
    binary = [1 if g >= 2 else 0 for g in retrieved_grades]
    relevant_ids = {doc for doc, g in grades.items() if g >= 2}
    ideal = [float(g) for g in grades.values() if g > 0] or [0.0]
    return {
        "precision@1": precision_at_k(binary, 1),
        "precision@3": precision_at_k(binary, 3),
        "precision@5": precision_at_k(binary, 5),
        "recall@5": recall_at_k(retrieved_ids, relevant_ids, 5),
        "recall@10": recall_at_k(retrieved_ids, relevant_ids, 10),
        "mrr": reciprocal_rank(binary),
        "map": average_precision(retrieved_ids, relevant_ids),
        "ndcg@5": ndcg_at_k(retrieved_grades, ideal, 5),
        "ndcg@10": ndcg_at_k(retrieved_grades, ideal, 10),
        "hit_rate": hit_rate(binary, TOP_K),
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, float]:
    keys = [
        "precision@1",
        "precision@3",
        "precision@5",
        "recall@5",
        "recall@10",
        "mrr",
        "map",
        "ndcg@5",
        "ndcg@10",
        "hit_rate",
        "latency_ms",
        "duplicate_rate",
        "source_diversity",
        "official_documentation_coverage",
        "github_incident_coverage",
        "product_knowledge_coverage",
    ]
    out: dict[str, float] = {}
    for key in keys:
        values = [float(r[key]) for r in rows if key in r]
        out[key] = round(mean(values), 4) if values else 0.0
    lats = sorted(float(r["latency_ms"]) for r in rows)
    out["p50_latency_ms"] = round(lats[len(lats) // 2], 4) if lats else 0.0
    out["p95_latency_ms"] = (
        round(lats[min(len(lats) - 1, int(0.95 * (len(lats) - 1)))], 4) if lats else 0.0
    )
    out["mean_latency_ms"] = out["latency_ms"]
    return out


def _evaluate_mode(
    *,
    name: str,
    queries: list[dict[str, str]],
    gold: dict[str, dict[str, int]],
    provider: Any,
    primary: ChromaVectorStore,
    secondary: ChromaVectorStore | None,
) -> tuple[dict[str, float], list[dict[str, Any]], dict[str, dict[str, float]]]:
    rows: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for query in queries:
        qid = query["query_id"]
        grades = gold.get(qid, {})
        masked, _ = mask_secrets(query["query_text"])
        started = time.perf_counter()
        embedding = provider.embed_query(masked)
        primary_hits = _query_store(primary, embedding, TOP_K)
        if secondary is None:
            hits = primary_hits[:TOP_K]
            raw_count = len(primary_hits)
        else:
            secondary_hits = _query_store(secondary, embedding, TOP_K)
            raw_count = len(primary_hits) + len(secondary_hits)
            hits = _merge_hits(primary_hits, secondary_hits, TOP_K)
        latency_ms = (time.perf_counter() - started) * 1000.0

        buckets = Counter(_source_bucket(h.metadata) for h in hits)
        duplicate_rate = 0.0 if raw_count == 0 else 1.0 - (len(hits) / float(raw_count))
        metrics = _metrics_for_hits(hits, grades)
        row = {
            "query_id": qid,
            "category_group": query.get("category_group") or "",
            "technology": query.get("technology") or "",
            **metrics,
            "latency_ms": round(latency_ms, 4),
            "duplicate_rate": round(max(0.0, duplicate_rate), 4),
            "source_diversity": float(len(buckets)),
            "official_documentation_coverage": 1.0 if buckets.get("official_docs") else 0.0,
            "github_incident_coverage": 1.0 if buckets.get("github_incident") else 0.0,
            "product_knowledge_coverage": 1.0 if buckets.get("product_knowledge") else 0.0,
            "top1": hits[0].chunk_id if hits else None,
            "top1_source": _source_bucket(hits[0].metadata) if hits else None,
        }
        rows.append(row)
        by_cat[row["category_group"]].append(row)
        if any(m in (query.get("technology") or "").lower() for m in REQUIRED_TECH_MARKERS) or any(
            m in (query.get("query_text") or "").lower() for m in REQUIRED_TECH_MARKERS
        ):
            examples.append(
                {
                    "mode": name,
                    "query_id": qid,
                    "query_text": query["query_text"][:160],
                    "top_ids": [h.chunk_id for h in hits[:5]],
                    "top_sources": [_source_bucket(h.metadata) for h in hits[:5]],
                }
            )

    aggregate = _aggregate(rows)
    category = {cat: _aggregate(items) for cat, items in sorted(by_cat.items())}
    return aggregate, examples, category


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    queries, gold = _load_gold()
    provider = build_embedding_provider(
        os.environ.get("EMBEDDING_PROVIDER", "sentence_transformers"),
        model=os.environ.get(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
        device=os.environ.get("EMBEDDING_DEVICE", "cpu"),  # type: ignore[arg-type]
        batch_size=int(os.environ.get("EMBEDDING_BATCH_SIZE", "16")),
        normalize=True,
        lazy_load=True,
    )
    identity = provider.config_identity() if hasattr(provider, "config_identity") else None
    host, port, persist = _chroma()
    primary = ChromaVectorStore(
        host=host,
        port=port,
        persist_path=persist,
        collection_name=PRIMARY_COLLECTION,
        embedding_identity=identity,
        connect_retries=3,
    )
    secondary = ChromaVectorStore(
        host=host,
        port=port,
        persist_path=persist,
        collection_name=SECONDARY_COLLECTION,
        embedding_identity=identity,
        connect_retries=3,
    )

    single_m, single_ex, single_cat = _evaluate_mode(
        name="single",
        queries=queries,
        gold=gold,
        provider=provider,
        primary=primary,
        secondary=None,
    )
    fed_m, fed_ex, fed_cat = _evaluate_mode(
        name="federated",
        queries=queries,
        gold=gold,
        provider=provider,
        primary=primary,
        secondary=secondary,
    )

    meta = {
        "primary_collection": PRIMARY_COLLECTION,
        "secondary_collection": SECONDARY_COLLECTION,
        "queries": len(queries),
        "top_k": TOP_K,
        "labels": "gold_labels.csv",
        "note": (
            "Mode A = labeled research collection only. "
            "Mode B = research + product knowledge merge/dedupe. "
            "Gold labels target research document IDs; product-only hits do not "
            "raise gold precision but may improve operational diagnosis coverage."
        ),
    }

    (OUT / "single_collection_metrics.json").write_text(
        json.dumps({"meta": meta, "metrics": single_m, "by_category": single_cat}, indent=2),
        encoding="utf-8",
    )
    (OUT / "federated_metrics.json").write_text(
        json.dumps({"meta": meta, "metrics": fed_m, "by_category": fed_cat}, indent=2),
        encoding="utf-8",
    )

    metric_keys = sorted(set(single_m) | set(fed_m))
    with (OUT / "comparison.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["metric", "single", "federated", "delta"])
        writer.writeheader()
        for key in metric_keys:
            a = float(single_m.get(key, 0.0))
            b = float(fed_m.get(key, 0.0))
            writer.writerow({"metric": key, "single": a, "federated": b, "delta": round(b - a, 4)})

    with (OUT / "category_comparison.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["category", "metric", "single", "federated", "delta"],
        )
        writer.writeheader()
        for cat in sorted(set(single_cat) | set(fed_cat)):
            for key in ("ndcg@5", "hit_rate", "mean_latency_ms", "product_knowledge_coverage"):
                a = float(single_cat.get(cat, {}).get(key, 0.0))
                b = float(fed_cat.get(cat, {}).get(key, 0.0))
                writer.writerow(
                    {
                        "category": cat,
                        "metric": key,
                        "single": a,
                        "federated": b,
                        "delta": round(b - a, 4),
                    }
                )

    with (OUT / "latency_comparison.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["metric", "single_ms", "federated_ms"],
        )
        writer.writeheader()
        for key in ("mean_latency_ms", "p50_latency_ms", "p95_latency_ms"):
            writer.writerow(
                {
                    "metric": key,
                    "single_ms": single_m.get(key, 0.0),
                    "federated_ms": fed_m.get(key, 0.0),
                }
            )

    # Decision based on measured evidence.
    quality_delta = fed_m["ndcg@5"] - single_m["ndcg@5"]
    latency_delta = fed_m["p95_latency_ms"] - single_m["p95_latency_ms"]
    product_gain = fed_m["product_knowledge_coverage"] - single_m["product_knowledge_coverage"]
    if quality_delta >= 0.01 and latency_delta < 50:
        decision = (
            "Prefer federated retrieval when a populated secondary collection is configured "
            f"(ndcg@5 +{quality_delta:.4f}, product coverage +{product_gain:.4f})."
        )
        default_mode = "federated_when_secondary_configured"
    elif product_gain >= 0.05 and quality_delta >= -0.02:
        decision = (
            "Keep primary-only as the hard default for gold IR metrics; enable optional "
            "federated mode via CHROMA_SECONDARY_COLLECTION_NAME for product-knowledge coverage."
        )
        default_mode = "primary_only_default_federated_optional"
    else:
        decision = (
            "Keep primary collection as default. Federated mode is optional and should remain "
            "disabled unless secondary corpus value outweighs added latency."
        )
        default_mode = "primary_only"

    (OUT / "comparison.md").write_text(
        "\n".join(
            [
                "# Retrieval Architecture Comparison",
                "",
                f"Primary: `{PRIMARY_COLLECTION}`",
                f"Secondary: `{SECONDARY_COLLECTION}`",
                f"Queries: {len(queries)} (gold labels)",
                "",
                "## Aggregate metrics",
                "",
                f"- Single: `{json.dumps(single_m)}`",
                f"- Federated: `{json.dumps(fed_m)}`",
                "",
                "## Decision",
                "",
                f"**Default mode:** `{default_mode}`",
                "",
                decision,
                "",
                "## Trade-offs",
                "",
                "- Federated merge increases latency (extra collection query + dedupe).",
                "- Gold labels score research document IDs; product chunks rarely raise Precision/nDCG.",
                "- Product secondary improves operational diagnosis grounding for live incidents.",
                "- Server flag / env controls federation; clients cannot bypass.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    example_lines = ["# Retrieval examples", ""]
    for ex in (single_ex + fed_ex)[:40]:
        example_lines.append(
            f"- [{ex['mode']}] {ex['query_id']}: top={ex['top_ids']} sources={ex['top_sources']}"
        )
    (OUT / "retrieval_examples.md").write_text("\n".join(example_lines) + "\n", encoding="utf-8")

    charts = OUT / "charts"
    charts.mkdir(exist_ok=True)
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        labels = ["p@1", "p@5", "ndcg@5", "hit", "prod_cov"]
        single_vals = [
            single_m["precision@1"],
            single_m["precision@5"],
            single_m["ndcg@5"],
            single_m["hit_rate"],
            single_m["product_knowledge_coverage"],
        ]
        fed_vals = [
            fed_m["precision@1"],
            fed_m["precision@5"],
            fed_m["ndcg@5"],
            fed_m["hit_rate"],
            fed_m["product_knowledge_coverage"],
        ]
        x = range(len(labels))
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar([i - 0.2 for i in x], single_vals, width=0.4, label="single")
        ax.bar([i + 0.2 for i in x], fed_vals, width=0.4, label="federated")
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels)
        ax.set_ylim(0, 1.05)
        ax.legend()
        ax.set_title("Single vs federated quality")
        fig.tight_layout()
        fig.savefig(charts / "quality_comparison.png")
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(
            ["single_p50", "single_p95", "fed_p50", "fed_p95"],
            [
                single_m["p50_latency_ms"],
                single_m["p95_latency_ms"],
                fed_m["p50_latency_ms"],
                fed_m["p95_latency_ms"],
            ],
        )
        ax.set_ylabel("Latency (ms)")
        ax.set_title("Latency comparison")
        fig.tight_layout()
        fig.savefig(charts / "latency_comparison.png")
        plt.close(fig)
    except Exception as exc:  # noqa: BLE001
        (OUT / "charts_error.txt").write_text(str(exc), encoding="utf-8")

    decision_payload = {
        "default_mode": default_mode,
        "decision": decision,
        "single": single_m,
        "federated": fed_m,
        "meta": meta,
    }
    (OUT / "decision.json").write_text(json.dumps(decision_payload, indent=2), encoding="utf-8")
    print(json.dumps({"default_mode": default_mode, "single_ndcg@5": single_m["ndcg@5"], "fed_ndcg@5": fed_m["ndcg@5"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
