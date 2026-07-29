"""Promote human-accepted review rows into official gold_labels.csv."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
BENCH = REPO_ROOT / "datasets" / "benchmark"
REVIEW = BENCH / "review"

GOLD_FIELDS = [
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
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def promote(
    *,
    reviewed_by: str,
    require_accept: bool = True,
    include_proposed_if_accepted: bool = True,
) -> dict[str, Any]:
    review_rows = _read_csv(REVIEW / "candidate_review.csv")
    if not review_rows:
        raise FileNotFoundError("Missing review/candidate_review.csv — run retrieve_candidates.py")

    accepted: list[dict[str, str]] = []
    now = datetime.now(UTC).isoformat()
    for row in review_rows:
        accept = (row.get("accept") or "").strip().upper()
        if require_accept and accept not in {"Y", "YES", "TRUE", "1"}:
            continue
        human = (row.get("human_relevance") or "").strip()
        proposed = (row.get("proposed_relevance") or "").strip()
        relevance = human if human != "" else (proposed if include_proposed_if_accepted else "")
        if relevance == "":
            continue
        grade = int(relevance)
        if grade < 0 or grade > 3:
            raise ValueError(f"Invalid relevance for {row.get('query_id')}: {relevance}")
        if grade == 0:
            # Optional: keep explicit negatives for analysis; include them.
            pass
        accepted.append(
            {
                "query_id": row["query_id"],
                "document_id": row["document_id"],
                "relevance": str(grade),
                "source_type": row.get("source_type") or "",
                "technology": row.get("technology") or "",
                "category": row.get("category") or "",
                "vendor": row.get("vendor") or "",
                "label_origin": "human_approved",
                "review_status": "approved",
                "reviewed_by": reviewed_by,
                "reviewed_at": now,
            }
        )

    gold_path = BENCH / "gold_labels.csv"
    existing = {
        (r["query_id"], r["document_id"]): r
        for r in _read_csv(gold_path)
        if r.get("query_id") and r.get("document_id")
    }
    for row in accepted:
        existing[(row["query_id"], row["document_id"])] = row

    merged = sorted(existing.values(), key=lambda r: (r["query_id"], r["document_id"]))
    with gold_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=GOLD_FIELDS)
        writer.writeheader()
        writer.writerows(merged)

    queries = {r["query_id"] for r in _read_csv(BENCH / "queries.csv")}
    covered = {r["query_id"] for r in merged if int(r.get("relevance") or 0) >= 2}
    summary = {
        "promoted_rows": len(accepted),
        "gold_rows_total": len(merged),
        "queries_with_relevant_ge_2": len(covered),
        "queries_total": len(queries),
        "queries_missing_relevant": sorted(queries - covered),
        "reviewed_by": reviewed_by,
        "gold_path": str(gold_path.relative_to(REPO_ROOT)),
    }
    (REVIEW / "promotion_report.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed-by", default="human_reviewer")
    parser.add_argument(
        "--allow-without-accept",
        action="store_true",
        help="Dangerous: promote all rows using human_relevance/proposed without accept=Y",
    )
    args = parser.parse_args(argv)
    summary = promote(
        reviewed_by=args.reviewed_by,
        require_accept=not args.allow_without_accept,
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["promoted_rows"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
