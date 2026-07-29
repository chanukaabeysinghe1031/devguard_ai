"""Retrieve top-K docs per benchmark query and propose candidate relevance grades.

IMPORTANT: Proposed grades are NOT official gold. Humans must review and approve
before writing ``gold_labels.csv``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
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

BENCH = REPO_ROOT / "datasets" / "benchmark"
REVIEW = BENCH / "review"


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
        normalize=os.environ.get("EMBEDDING_NORMALIZE", "true").lower()
        in {"1", "true", "yes", "on"},
        lazy_load=True,
    )


def _load_queries() -> list[dict[str, str]]:
    path = BENCH / "queries.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _token_set(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) > 2}


def propose_relevance(query: dict[str, str], hit_meta: dict[str, Any], text: str) -> int:
    """Heuristic proposal only — for human review, not dissertation gold."""
    expected_techs = {
        t.strip().lower()
        for t in (query.get("expected_technologies") or "").split("|")
        if t.strip()
    }
    tech = str(hit_meta.get("technology") or "").lower()
    category = str(
        hit_meta.get("failure_category") or hit_meta.get("category") or ""
    ).lower()
    expected_cat = str(query.get("failure_category") or "").lower()
    q_tokens = _token_set(query.get("query_text") or "")
    d_tokens = _token_set(text[:2000])
    overlap = len(q_tokens & d_tokens) / float(max(1, len(q_tokens)))

    tech_match = bool(tech and tech in expected_techs)
    cat_match = bool(expected_cat and category == expected_cat)

    if tech_match and cat_match and overlap >= 0.15:
        return 3
    if tech_match and (cat_match or overlap >= 0.2):
        return 2
    if tech_match or cat_match or overlap >= 0.25:
        return 1
    if overlap >= 0.12:
        return 1
    return 0


def retrieve_and_propose(*, top_k: int, collection: str) -> dict[str, Any]:
    if collection == "devguard_knowledge":
        raise RuntimeError("Refusing to use product collection")

    queries = _load_queries()
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

    REVIEW.mkdir(parents=True, exist_ok=True)
    by_query = REVIEW / "by_query"
    by_query.mkdir(parents=True, exist_ok=True)

    review_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    for query in queries:
        masked, _ = mask_secrets(query["query_text"])
        embedding = provider.embed_query(masked)
        hits = store.query(embedding=embedding, top_k=top_k)
        md_lines = [
            f"# Review: {query['query_id']}",
            "",
            f"**Query:** {query['query_text']}",
            f"**Category:** {query['category_group']} / {query['failure_category']}",
            f"**Difficulty:** {query['difficulty']}",
            "",
            "Fill `human_relevance` (0–3) and set `accept` to `Y` when approved.",
            "",
            "| rank | chunk_id | proposed | human | accept | score | source | tech | snippet |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for rank, hit in enumerate(hits, start=1):
            meta = dict(hit.metadata or {})
            proposed = propose_relevance(query, meta, hit.text or "")
            snippet = re.sub(r"\s+", " ", (hit.text or "")[:160]).strip()
            row = {
                "query_id": query["query_id"],
                "rank": rank,
                "document_id": hit.chunk_id,
                "proposed_relevance": proposed,
                "human_relevance": "",
                "accept": "",
                "score": round(float(hit.score), 4),
                "source_type": meta.get("source_type") or "",
                "technology": meta.get("technology") or "",
                "category": meta.get("failure_category")
                or meta.get("category")
                or "",
                "vendor": meta.get("vendor") or "",
                "snippet": snippet,
            }
            review_rows.append(row)
            if proposed >= 1:
                candidate_rows.append(
                    {
                        "query_id": query["query_id"],
                        "document_id": hit.chunk_id,
                        "relevance": proposed,
                        "source_type": row["source_type"],
                        "technology": row["technology"],
                        "category": row["category"] or query["failure_category"],
                        "vendor": row["vendor"],
                        "label_origin": "candidate_heuristic_v1",
                        "review_status": "pending_human_review",
                    }
                )
            md_lines.append(
                f"| {rank} | `{hit.chunk_id}` | {proposed} |  |  | {row['score']} | "
                f"{row['source_type']} | {row['technology']} | {snippet.replace('|', '/')} |"
            )
        (by_query / f"{query['query_id']}.md").write_text(
            "\n".join(md_lines) + "\n", encoding="utf-8"
        )

    review_path = REVIEW / "candidate_review.csv"
    with review_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "query_id",
                "rank",
                "document_id",
                "proposed_relevance",
                "human_relevance",
                "accept",
                "score",
                "source_type",
                "technology",
                "category",
                "vendor",
                "snippet",
            ],
        )
        writer.writeheader()
        writer.writerows(review_rows)

    cand_path = BENCH / "gold_labels.candidates.csv"
    with cand_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "query_id",
                "document_id",
                "relevance",
                "source_type",
                "technology",
                "category",
                "vendor",
                "label_origin",
                "review_status",
            ],
        )
        writer.writeheader()
        writer.writerows(candidate_rows)

    # Official gold starts empty until human promotion.
    gold_path = BENCH / "gold_labels.csv"
    if not gold_path.exists():
        with gold_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "query_id",
                    "document_id",
                    "relevance",
                    "source_type",
                    "technology",
                    "category",
                    "vendor",
                    "label_origin",
                    "review_status",
                    "reviewed_by",
                    "reviewed_at",
                ],
            )
            writer.writeheader()

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "queries": len(queries),
        "review_rows": len(review_rows),
        "candidate_positive_labels": len(candidate_rows),
        "top_k": top_k,
        "collection": collection,
        "review_csv": str(review_path.relative_to(REPO_ROOT)),
        "candidates_csv": str(cand_path.relative_to(REPO_ROOT)),
        "note": "Candidates are NOT human gold. Promote via promote_labels.py after review.",
    }
    (REVIEW / "candidate_generation_report.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    (REVIEW / "APPROVAL_INSTRUCTIONS.md").write_text(
        """# Human approval instructions

1. Open `candidate_review.csv` (or per-query markdown under `by_query/`).
2. For each row, set `human_relevance` to 0–3 (or leave blank to keep proposed).
3. Set `accept` to `Y` for rows that should enter official gold.
4. Prefer at least one grade ≥2 per query when evidence exists.
5. Run:

```bash
backend/.venv/bin/python scripts/dataset/benchmark/promote_labels.py
```

6. Re-run evaluation against `gold_labels.csv` (default).

Academic note: dissertation claims of human-validated gold require this approval step.
""",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--collection", default="devguard_research_knowledge")
    args = parser.parse_args(argv)
    summary = retrieve_and_propose(top_k=args.top_k, collection=args.collection)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
