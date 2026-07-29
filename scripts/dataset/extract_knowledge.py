#!/usr/bin/env python3
"""Phase 3 — extract structured knowledge from sanitised incidents.

Reads datasets/sanitized/github (+ optional github_open), extracts symptoms /
root_cause / resolution heuristically, refines failure_category, and writes:

- datasets/labelled/github/*.json          (updated incident records)
- datasets/processed/knowledge/*.json      (knowledge records for later chunking)
- datasets/reports/phase3_extract_report.json

Does not embed, ingest to Chroma, or call OpenAI.

Usage:

  python scripts/dataset/extract_knowledge.py
  python scripts/dataset/extract_knowledge.py --skip-open --max-curated 450
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from knowledge_extraction import (  # noqa: E402
    extract_knowledge,
    to_knowledge_record,
)

DEFAULT_CLOSED_IN = REPO_ROOT / "datasets" / "sanitized" / "github"
DEFAULT_OPEN_IN = REPO_ROOT / "datasets" / "sanitized" / "github_open"
DEFAULT_LABELLED_CLOSED = REPO_ROOT / "datasets" / "labelled" / "github"
DEFAULT_LABELLED_OPEN = REPO_ROOT / "datasets" / "labelled" / "github_open"
DEFAULT_KNOWLEDGE = REPO_ROOT / "datasets" / "processed" / "knowledge"
DEFAULT_REPORTS = REPO_ROOT / "datasets" / "reports"
VERSION_PATH = REPO_ROOT / "datasets" / "VERSION"


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _iter_incidents(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("gh-*.json") if p.is_file())


def _clear_json_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in root.rglob("*.json"):
        path.unlink()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def process_pool(
    *,
    input_root: Path,
    labelled_root: Path,
    knowledge_root: Path | None,
    source_pool: str,
    dataset_version: str,
    max_curated: int | None,
    allow_curated: bool,
    stats: dict[str, Any],
) -> None:
    files = _iter_incidents(input_root)
    labelled_root.mkdir(parents=True, exist_ok=True)
    if knowledge_root is not None:
        knowledge_root.mkdir(parents=True, exist_ok=True)

    manifest_path = labelled_root / f"{source_pool}_labelled_manifest.jsonl"
    if manifest_path.exists():
        manifest_path.unlink()

    curated_count = 0
    with manifest_path.open("a", encoding="utf-8") as manifest:
        for path in files:
            incident = json.loads(path.read_text(encoding="utf-8"))
            # Ensure pool marker present for open/closed logic.
            raw_meta = dict(incident.get("raw_metadata") or {})
            raw_meta.setdefault("phase2_source_pool", source_pool)
            incident["raw_metadata"] = raw_meta

            extraction = extract_knowledge(incident)
            stats["processed"] += 1
            stats["confidence"][extraction.confidence] += 1
            stats["status"][extraction.status] += 1
            stats["category"][extraction.failure_category] += 1
            stats["technology"][str(incident.get("technology") or "other")] += 1

            status = extraction.status
            if status == "rejected":
                stats["rejected"] += 1
                continue

            if status == "curated":
                if not allow_curated:
                    status = "curation_candidate"
                elif max_curated is not None and curated_count >= max_curated:
                    status = "curation_candidate"
                    stats["curated_capped"] += 1
                else:
                    curated_count += 1
                    stats["curated"] += 1

            incident["symptoms"] = extraction.symptoms
            incident["root_cause"] = extraction.root_cause
            incident["resolution"] = extraction.resolution
            incident["failure_category"] = extraction.failure_category

            collection = dict(incident.get("collection") or {})
            collection["dataset_version"] = dataset_version
            collection["status"] = status
            collection["curation_notes"] = (
                f"phase3_heuristic_v1; confidence={extraction.confidence}; "
                f"score={extraction.score}; sections={extraction.sections_found}"
            )
            incident["collection"] = collection

            provenance = dict(incident.get("provenance") or {})
            provenance["modified"] = True
            incident["provenance"] = provenance

            raw_meta["phase3_confidence"] = extraction.confidence
            raw_meta["phase3_score"] = extraction.score
            incident["raw_metadata"] = raw_meta

            repo = str(incident.get("repository") or "unknown").replace("/", "_")
            out_incident = labelled_root / repo / f"{incident['incident_id']}.json"
            _write_json(out_incident, incident)

            knowledge = None
            if knowledge_root is not None and status in {"curated", "curation_candidate"}:
                knowledge = to_knowledge_record(incident, extraction)
                # Prefer writing curated knowledge docs; candidates also kept for review.
                kn_name = f"{knowledge['knowledge_id']}.json"
                if status == "curated":
                    _write_json(knowledge_root / "curated" / kn_name, knowledge)
                    stats["knowledge_curated"] += 1
                else:
                    _write_json(knowledge_root / "candidates" / kn_name, knowledge)
                    stats["knowledge_candidates"] += 1

            manifest.write(
                json.dumps(
                    {
                        "path": _rel(out_incident),
                        "incident_id": incident["incident_id"],
                        "status": status,
                        "confidence": extraction.confidence,
                        "score": extraction.score,
                        "failure_category": extraction.failure_category,
                        "has_root_cause": bool(extraction.root_cause),
                        "has_resolution": bool(extraction.resolution),
                        "knowledge_id": None if knowledge is None else knowledge["knowledge_id"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--closed-in", type=Path, default=DEFAULT_CLOSED_IN)
    parser.add_argument("--open-in", type=Path, default=DEFAULT_OPEN_IN)
    parser.add_argument("--labelled-closed", type=Path, default=DEFAULT_LABELLED_CLOSED)
    parser.add_argument("--labelled-open", type=Path, default=DEFAULT_LABELLED_OPEN)
    parser.add_argument("--knowledge-out", type=Path, default=DEFAULT_KNOWLEDGE)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument("--max-curated", type=int, default=500)
    parser.add_argument("--skip-open", action="store_true")
    args = parser.parse_args(argv)

    dataset_version = "0.3.0-phase3"
    stats: dict[str, Any] = {
        "processed": 0,
        "rejected": 0,
        "curated": 0,
        "curated_capped": 0,
        "knowledge_curated": 0,
        "knowledge_candidates": 0,
        "confidence": Counter(),
        "status": Counter(),
        "category": Counter(),
        "technology": Counter(),
    }

    for root in (
        args.labelled_closed,
        args.labelled_open,
        args.knowledge_out / "curated",
        args.knowledge_out / "candidates",
    ):
        root.mkdir(parents=True, exist_ok=True)
        _clear_json_tree(root)

    process_pool(
        input_root=args.closed_in,
        labelled_root=args.labelled_closed,
        knowledge_root=args.knowledge_out,
        source_pool="closed",
        dataset_version=dataset_version,
        max_curated=args.max_curated,
        allow_curated=True,
        stats=stats,
    )

    if not args.skip_open:
        process_pool(
            input_root=args.open_in,
            labelled_root=args.labelled_open,
            knowledge_root=args.knowledge_out,
            source_pool="open",
            dataset_version=dataset_version,
            max_curated=0,
            allow_curated=False,
            stats=stats,
        )

    report = {
        "phase": 3,
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_version": dataset_version,
        "method": "heuristic_v1",
        "counts": {
            "processed": stats["processed"],
            "rejected": stats["rejected"],
            "curated": stats["curated"],
            "curated_capped_to_candidate": stats["curated_capped"],
            "knowledge_curated": stats["knowledge_curated"],
            "knowledge_candidates": stats["knowledge_candidates"],
            "confidence": dict(stats["confidence"].most_common()),
            "status_seen": dict(stats["status"].most_common()),
            "failure_category": dict(stats["category"].most_common()),
            "technology": dict(stats["technology"].most_common()),
        },
        "outputs": {
            "labelled_closed": _rel(args.labelled_closed),
            "labelled_open": _rel(args.labelled_open),
            "knowledge_curated": _rel(args.knowledge_out / "curated"),
            "knowledge_candidates": _rel(args.knowledge_out / "candidates"),
        },
        "notes": [
            "Auto-curated means heuristic extraction found symptoms plus root cause and/or resolution.",
            "Human review can promote candidates or correct categories before chunking.",
            "Open issues are never auto-marked curated for the RAG knowledge corpus.",
        ],
    }
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.reports_dir / "phase3_extract_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    VERSION_PATH.write_text(f"{dataset_version}\n", encoding="utf-8")

    print(json.dumps(report["counts"], indent=2))
    print(f"report={_rel(report_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
