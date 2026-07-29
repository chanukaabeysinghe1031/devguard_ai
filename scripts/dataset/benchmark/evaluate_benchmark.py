#!/usr/bin/env python3
"""Evaluate a retriever against the DevGuard human-gold retrieval benchmark.

Defaults to official ``gold_labels.csv``. Use ``--labels candidates`` only for
pre-approval smoke tests — candidate labels are not dissertation gold.
"""

from __future__ import annotations

# ruff: noqa: I001

import argparse
import csv
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
SCRIPT_DIR = Path(__file__).resolve().parent
DATASET_SCRIPT = REPO_ROOT / "scripts" / "dataset"
for path in (BACKEND_ROOT, DATASET_SCRIPT, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.ai.rag.embedding_provider import build_embedding_provider  # noqa: E402
from app.ai.rag.vector_store import ChromaVectorStore  # noqa: E402
from app.domain.services.secret_masker import mask_secrets  # noqa: E402
from metrics import (  # noqa: E402, I001
    average_precision,
    hit_rate,
    mean,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

BENCH = REPO_ROOT / "datasets" / "benchmark"
RESULTS = BENCH / "results"


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
    return build_embedding_provider(
        os.environ.get("EMBEDDING_PROVIDER", "sentence_transformers"),
        model=os.environ.get(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
        device=os.environ.get("EMBEDDING_DEVICE", "cpu"),  # type: ignore[arg-type]
        batch_size=int(os.environ.get("EMBEDDING_BATCH_SIZE", "16")),
        normalize=True,
        lazy_load=True,
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_benchmark(*, labels_mode: str) -> tuple[list[dict[str, str]], dict[str, dict[str, int]]]:
    queries = _read_csv(BENCH / "queries.csv")
    if labels_mode == "candidates":
        label_path = BENCH / "gold_labels.candidates.csv"
    else:
        label_path = BENCH / "gold_labels.csv"
    if not label_path.exists():
        raise FileNotFoundError(f"Missing labels file: {label_path}")
    labels = _read_csv(label_path)
    gold: dict[str, dict[str, int]] = defaultdict(dict)
    for row in labels:
        qid = row.get("query_id") or ""
        doc = row.get("document_id") or ""
        if not qid or not doc:
            continue
        gold[qid][doc] = int(row.get("relevance") or 0)
    return queries, dict(gold)


def validate_benchmark(
    queries: list[dict[str, str]],
    gold: dict[str, dict[str, int]],
    *,
    require_relevant: bool,
) -> dict[str, Any]:
    query_ids = [q["query_id"] for q in queries]
    dupes = [qid for qid, n in Counter(query_ids).items() if n > 1]
    missing_relevant = [
        qid
        for qid in query_ids
        if not any(grade >= 2 for grade in gold.get(qid, {}).values())
    ]
    orphan_docs = []  # filled after retrieval optional; structural orphans = none yet
    return {
        "duplicate_query_ids": dupes,
        "queries_missing_relevant_ge_2": missing_relevant if require_relevant else [],
        "orphan_document_ids": orphan_docs,
        "ok": not dupes and (not require_relevant or not missing_relevant),
    }


def evaluate(
    *,
    collection: str,
    top_k: int,
    labels_mode: str,
    output_dir: Path,
    save_json: bool,
    save_markdown: bool,
    save_charts: bool,
) -> dict[str, Any]:
    if collection == "devguard_knowledge":
        raise RuntimeError("Refusing to evaluate against product collection")

    config = json.loads((BENCH / "evaluation_config.json").read_text(encoding="utf-8"))
    meta = json.loads((BENCH / "benchmark_metadata.json").read_text(encoding="utf-8"))
    queries, gold = load_benchmark(labels_mode=labels_mode)
    validation = validate_benchmark(
        queries, gold, require_relevant=(labels_mode == "gold")
    )

    provider = _embedding_provider()
    identity = provider.config_identity() if hasattr(provider, "config_identity") else None
    host, port, persist = _chroma_settings()
    store = ChromaVectorStore(
        host=host,
        port=port,
        persist_path=persist,
        collection_name=collection,
        embedding_identity=identity,
        connect_retries=3,
    )

    per_query: list[dict[str, Any]] = []
    false_positives: list[dict[str, Any]] = []
    false_negatives: list[dict[str, Any]] = []
    tech_confusion: Counter[str] = Counter()
    category_confusion: Counter[str] = Counter()
    missing_docs = 0
    missing_incidents = 0

    for query in queries:
        qid = query["query_id"]
        grades = gold.get(qid, {})
        relevant_ids = {doc for doc, g in grades.items() if g >= 2}
        all_graded = grades

        masked, _ = mask_secrets(query["query_text"])
        started = time.perf_counter()
        embedding = provider.embed_query(masked)
        hits = store.query(embedding=embedding, top_k=max(top_k, 10))
        latency_ms = (time.perf_counter() - started) * 1000.0

        retrieved_ids = [h.chunk_id for h in hits]
        retrieved_grades = [float(all_graded.get(doc, 0)) for doc in retrieved_ids]
        binary = [1 if g >= 2 else 0 for g in retrieved_grades]
        ideal = [float(g) for g in all_graded.values() if g > 0] or [0.0]

        expected_techs = {
            t.strip().lower()
            for t in (query.get("expected_technologies") or "").split("|")
            if t.strip()
        }
        category_hit = any(
            str(
                (h.metadata or {}).get("failure_category")
                or (h.metadata or {}).get("category")
                or ""
            )
            == query.get("failure_category")
            for h in hits[:top_k]
        )
        vendor_hit = False
        expected_vendors = {
            v.strip().lower()
            for v in (query.get("expected_vendors") or "").split("|")
            if v.strip()
        }
        for h in hits[:top_k]:
            vendor = str((h.metadata or {}).get("vendor") or "").lower()
            if vendor and vendor in expected_vendors:
                vendor_hit = True
                break
            # GitHub incidents often lack vendor; technology proxy for coverage.
            tech = str((h.metadata or {}).get("technology") or "").lower()
            if tech and tech in expected_techs:
                vendor_hit = True
                break

        metrics_q = {
            "precision@1": precision_at_k(binary, 1),
            "precision@3": precision_at_k(binary, 3),
            "precision@5": precision_at_k(binary, 5),
            "recall@5": recall_at_k(retrieved_ids, relevant_ids, 5),
            "recall@10": recall_at_k(retrieved_ids, relevant_ids, 10),
            "mrr": reciprocal_rank(binary),
            "map": average_precision(retrieved_ids, relevant_ids),
            "ndcg@5": ndcg_at_k(retrieved_grades, ideal, 5),
            "ndcg@10": ndcg_at_k(retrieved_grades, ideal, 10),
            "hit_rate": hit_rate(binary, top_k),
            "latency_ms": round(latency_ms, 2),
            "category_accuracy": 1.0 if category_hit else 0.0,
            "vendor_coverage": 1.0 if vendor_hit else 0.0,
        }

        # Error analysis
        for rank, hit in enumerate(hits[:top_k], start=1):
            grade = all_graded.get(hit.chunk_id, 0)
            hit_meta = hit.metadata or {}
            tech = str(hit_meta.get("technology") or "").lower()
            if grade < 2 and any(t in (hit.text or "").lower() for t in ["lorem"]):
                pass
            if grade < 2 and tech and expected_techs and tech not in expected_techs:
                tech_confusion[f"{query.get('technology')}->{tech}"] += 1
            cat = str(hit_meta.get("failure_category") or hit_meta.get("category") or "")
            if grade < 2 and cat and cat != query.get("failure_category"):
                category_confusion[f"{query.get('failure_category')}->{cat}"] += 1
            if grade < 2 and rank <= 5:
                false_positives.append(
                    {
                        "query_id": qid,
                        "document_id": hit.chunk_id,
                        "rank": rank,
                        "score": round(float(hit.score), 4),
                        "source_type": hit_meta.get("source_type"),
                        "technology": tech,
                    }
                )
        for doc_id, grade in all_graded.items():
            if grade >= 2 and doc_id not in retrieved_ids[:10]:
                false_negatives.append(
                    {
                        "query_id": qid,
                        "document_id": doc_id,
                        "relevance": grade,
                    }
                )
                if str(doc_id).startswith("doc-"):
                    missing_docs += 1
                elif str(doc_id).startswith("kn-gh-"):
                    missing_incidents += 1

        per_query.append(
            {
                "query_id": qid,
                "query_text": query["query_text"],
                "category_group": query["category_group"],
                "technology": query["technology"],
                "difficulty": query["difficulty"],
                "gold_relevant_count": len(relevant_ids),
                "retrieved": [
                    {
                        "rank": i + 1,
                        "document_id": h.chunk_id,
                        "score": round(float(h.score), 4),
                        "source_type": (h.metadata or {}).get("source_type"),
                        "technology": (h.metadata or {}).get("technology"),
                        "vendor": (h.metadata or {}).get("vendor"),
                        "gold_relevance": all_graded.get(h.chunk_id, 0),
                    }
                    for i, h in enumerate(hits[: max(top_k, 10)])
                ],
                "metrics": metrics_q,
            }
        )

    aggregate = {
        key: round(mean(q["metrics"][key] for q in per_query), 4)
        for key in per_query[0]["metrics"]
    } if per_query else {}

    # Category reports
    by_category: dict[str, Any] = {}
    for group in sorted({q["category_group"] for q in queries}):
        subset = [q for q in per_query if q["category_group"] == group]
        if not subset:
            continue
        scored = sorted(subset, key=lambda q: q["metrics"]["ndcg@5"])
        by_category[group] = {
            "query_count": len(subset),
            "precision@5": round(mean(q["metrics"]["precision@5"] for q in subset), 4),
            "recall@5": round(mean(q["metrics"]["recall@5"] for q in subset), 4),
            "mrr": round(mean(q["metrics"]["mrr"] for q in subset), 4),
            "ndcg@5": round(mean(q["metrics"]["ndcg@5"] for q in subset), 4),
            "average_latency_ms": round(
                mean(q["metrics"]["latency_ms"] for q in subset), 2
            ),
            "worst_queries": [
                {
                    "query_id": q["query_id"],
                    "ndcg@5": q["metrics"]["ndcg@5"],
                    "query_text": q["query_text"],
                }
                for q in scored[:3]
            ],
            "best_queries": [
                {
                    "query_id": q["query_id"],
                    "ndcg@5": q["metrics"]["ndcg@5"],
                    "query_text": q["query_text"],
                }
                for q in scored[-3:][::-1]
            ],
        }

    error_analysis = {
        "false_positives_top5_count": len(false_positives),
        "false_negatives_count": len(false_negatives),
        "false_positives_sample": false_positives[:50],
        "false_negatives_sample": false_negatives[:50],
        "missing_documentation_signals": missing_docs,
        "missing_incident_signals": missing_incidents,
        "technology_confusion_top": tech_confusion.most_common(20),
        "category_confusion_top": category_confusion.most_common(20),
    }

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_dir / f"run_{stamp}_{labels_mode}"
    run_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "evaluation_date": datetime.now(UTC).isoformat(),
        "benchmark_version": meta.get("benchmark_version"),
        "corpus_version": meta.get("corpus_version_target"),
        "labels_mode": labels_mode,
        "collection": collection,
        "top_k": top_k,
        "embedding_model": config.get("embedding_model"),
        "embedding_dimension": config.get("embedding_dimension"),
        "retriever_version": config.get("retriever_version"),
        "query_count": len(queries),
        "validation": validation,
        "aggregate_metrics": aggregate,
        "latency_ms": {
            "mean": round(mean(q["metrics"]["latency_ms"] for q in per_query), 2)
            if per_query
            else 0,
            "p50": round(
                statistics.median(q["metrics"]["latency_ms"] for q in per_query), 2
            )
            if per_query
            else 0,
        },
        "category_reports": by_category,
        "per_query": per_query,
        "error_analysis": error_analysis,
    }

    if save_json:
        _write_json(run_dir / "metrics.json", report)
        _write_json(run_dir / "error_analysis.json", error_analysis)
        _write_json(run_dir / "category_reports.json", by_category)
        with (run_dir / "metrics.csv").open("w", encoding="utf-8", newline="") as handle:
            fields = [
                "query_id",
                "category_group",
                "difficulty",
                "precision@5",
                "recall@5",
                "mrr",
                "map",
                "ndcg@5",
                "hit_rate",
                "latency_ms",
            ]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for q in per_query:
                writer.writerow(
                    {
                        "query_id": q["query_id"],
                        "category_group": q["category_group"],
                        "difficulty": q["difficulty"],
                        **{k: q["metrics"][k] for k in fields[3:]},
                    }
                )

    if save_markdown:
        lines = [
            f"# Benchmark evaluation ({labels_mode})",
            "",
            f"- Benchmark version: `{report['benchmark_version']}`",
            f"- Corpus version: `{report['corpus_version']}`",
            f"- Collection: `{collection}`",
            f"- Queries: {len(queries)}",
            f"- Labels mode: **{labels_mode}**",
            "",
            "## Aggregate metrics",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
        ]
        for key, value in aggregate.items():
            lines.append(f"| {key} | {value} |")
        lines.extend(["", "## Category reports", ""])
        for group, payload in by_category.items():
            lines.append(f"### {group}")
            lines.append(
                f"- P@5={payload['precision@5']} R@5={payload['recall@5']} "
                f"MRR={payload['mrr']} nDCG@5={payload['ndcg@5']} "
                f"latency_ms={payload['average_latency_ms']}"
            )
            lines.append("")
        if labels_mode != "gold":
            lines.extend(
                [
                    "",
                    "> **Warning:** candidate labels are not human-approved gold.",
                    "",
                ]
            )
        (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if save_charts:
        try:
            from charts import render_charts

            chart_paths = render_charts(report, run_dir / "charts")
            report["charts_dir"] = str((run_dir / "charts").relative_to(REPO_ROOT))
            report["charts"] = [str(Path(p).name) for p in chart_paths]
        except Exception as exc:  # noqa: BLE001
            report["charts_error"] = str(exc)
        # Persist chart metadata after generation.
        if save_json:
            _write_json(run_dir / "metrics.json", report)

    # Latest pointer
    _write_json(output_dir / "latest_metrics.json", {
        "run_dir": str(run_dir.relative_to(REPO_ROOT)),
        "labels_mode": labels_mode,
        "aggregate_metrics": aggregate,
        "validation": validation,
        "benchmark_version": report["benchmark_version"],
    })
    report["run_dir"] = str(run_dir.relative_to(REPO_ROOT))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--collection", default="devguard_research_knowledge")
    parser.add_argument("--benchmark", default=None, help="Benchmark root directory")
    parser.add_argument("--output", default=None, help="Results output directory")
    parser.add_argument(
        "--labels",
        choices=("gold", "candidates"),
        default="gold",
        help="gold=human-approved official labels; candidates=pre-approval smoke only",
    )
    parser.add_argument("--save-json", action="store_true")
    parser.add_argument("--save-markdown", action="store_true")
    parser.add_argument("--save-charts", action="store_true")
    args = parser.parse_args(argv)

    # Re-bind module paths when a future corpus/benchmark root is supplied.
    global BENCH, RESULTS
    if args.benchmark:
        BENCH = Path(args.benchmark)
    RESULTS = Path(args.output) if args.output else BENCH / "results"
    output_dir = RESULTS

    report = evaluate(
        collection=args.collection,
        top_k=args.top_k,
        labels_mode=args.labels,
        output_dir=output_dir,
        save_json=True,
        save_markdown=True,
        save_charts=bool(args.save_charts),
    )
    print(
        json.dumps(
            {
                "run_dir": report.get("run_dir"),
                "labels_mode": report["labels_mode"],
                "aggregate_metrics": report["aggregate_metrics"],
                "validation": report["validation"],
            },
            indent=2,
        )
    )
    if args.labels == "gold" and not report["validation"]["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
