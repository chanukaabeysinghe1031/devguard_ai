#!/usr/bin/env python3
"""Phase 2 — clean and normalise raw GitHub incident JSON.

Reads datasets/raw/github (closed knowledge candidates) and optionally
datasets/raw/github_open (eval/symptoms). Writes kept incidents to
datasets/sanitized/... and a quality report under datasets/reports/.

Does not embed, ingest to Chroma, or call OpenAI.

Usage (from repo root):

  python scripts/dataset/clean_incidents.py
  python scripts/dataset/clean_incidents.py --include-open
  python scripts/dataset/validate_incidents.py datasets/sanitized
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
BACKEND_ROOT = REPO_ROOT / "backend"
SCRIPT_DIR = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.domain.services.secret_masker import mask_secrets  # noqa: E402
from cleaning import clean_incident  # noqa: E402

DEFAULT_CLOSED_IN = REPO_ROOT / "datasets" / "raw" / "github"
DEFAULT_OPEN_IN = REPO_ROOT / "datasets" / "raw" / "github_open"
DEFAULT_CLOSED_OUT = REPO_ROOT / "datasets" / "sanitized" / "github"
DEFAULT_OPEN_OUT = REPO_ROOT / "datasets" / "sanitized" / "github_open"
DEFAULT_REPORTS = REPO_ROOT / "datasets" / "reports"
VERSION_PATH = REPO_ROOT / "datasets" / "VERSION"


def _read_version() -> str:
    if VERSION_PATH.exists():
        return VERSION_PATH.read_text(encoding="utf-8").strip() or "0.2.0-phase2"
    return "0.2.0-phase2"


def _iter_incidents(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("gh-*.json") if p.is_file())


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("root must be object")
    return data


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def process_pool(
    *,
    input_root: Path,
    output_root: Path,
    source_pool: str,
    dataset_version: str,
    seen_hashes: set[str],
    rejected_rows: list[dict[str, Any]],
    reject_reasons: Counter[str],
    tech_kept: Counter[str],
    tech_rejected: Counter[str],
) -> tuple[int, int]:
    files = _iter_incidents(input_root)
    kept = 0
    rejected = 0
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / f"{source_pool}_sanitized_manifest.jsonl"
    # Fresh manifest for this run.
    if manifest_path.exists():
        manifest_path.unlink()

    with manifest_path.open("a", encoding="utf-8") as manifest:
        for path in files:
            try:
                raw = _load(path)
            except Exception as exc:  # noqa: BLE001
                rejected += 1
                reject_reasons["invalid_json"] += 1
                rejected_rows.append(
                    {
                        "path": _rel(path),
                        "reason": "invalid_json",
                        "detail": type(exc).__name__,
                        "source_pool": source_pool,
                    }
                )
                continue

            result = clean_incident(
                raw,
                source_pool=source_pool,
                dataset_version=dataset_version,
                mask_secrets_fn=mask_secrets,
                seen_hashes=seen_hashes,
            )
            tech = str(raw.get("technology") or "other")
            if not result.kept or result.incident is None:
                rejected += 1
                reason = result.reject_reason or "rejected"
                reject_reasons[reason] += 1
                tech_rejected[tech] += 1
                rejected_rows.append(
                    {
                        "path": _rel(path),
                        "incident_id": raw.get("incident_id"),
                        "title": (raw.get("title") or "")[:120],
                        "reason": reason,
                        "source_pool": source_pool,
                        "technology": tech,
                        "content_hash": result.content_hash,
                    }
                )
                continue

            incident = result.incident
            repo = str(incident.get("repository") or "unknown").replace("/", "_")
            out_dir = output_root / repo
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{incident['incident_id']}.json"
            out_path.write_text(
                json.dumps(incident, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            manifest.write(
                json.dumps(
                    {
                        "path": _rel(out_path),
                        "incident_id": incident["incident_id"],
                        "repository": incident.get("repository"),
                        "technology": incident.get("technology"),
                        "failure_category": incident.get("failure_category"),
                        "resolved": incident.get("resolved"),
                        "source_pool": source_pool,
                        "content_hash": result.content_hash,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            kept += 1
            tech_kept[tech] += 1

    return kept, rejected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--closed-in", type=Path, default=DEFAULT_CLOSED_IN)
    parser.add_argument("--open-in", type=Path, default=DEFAULT_OPEN_IN)
    parser.add_argument("--closed-out", type=Path, default=DEFAULT_CLOSED_OUT)
    parser.add_argument("--open-out", type=Path, default=DEFAULT_OPEN_OUT)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument(
        "--include-open",
        action="store_true",
        default=True,
        help="Also clean datasets/raw/github_open (default: on)",
    )
    parser.add_argument(
        "--skip-open",
        action="store_true",
        help="Clean only the closed knowledge pool",
    )
    args = parser.parse_args(argv)

    include_open = args.include_open and not args.skip_open
    dataset_version = _read_version()
    if "phase1" in dataset_version and "phase2" not in dataset_version:
        dataset_version = "0.2.0-phase2"

    seen_hashes: set[str] = set()
    rejected_rows: list[dict[str, Any]] = []
    reject_reasons: Counter[str] = Counter()
    tech_kept: Counter[str] = Counter()
    tech_rejected: Counter[str] = Counter()

    # Clear previous sanitized outputs for a deterministic rebuild.
    for out_root in (args.closed_out, args.open_out):
        if out_root.exists():
            for old in out_root.rglob("gh-*.json"):
                old.unlink()

    closed_kept, closed_rejected = process_pool(
        input_root=args.closed_in,
        output_root=args.closed_out,
        source_pool="closed",
        dataset_version=dataset_version,
        seen_hashes=seen_hashes,
        rejected_rows=rejected_rows,
        reject_reasons=reject_reasons,
        tech_kept=tech_kept,
        tech_rejected=tech_rejected,
    )

    open_kept = open_rejected = 0
    if include_open:
        open_kept, open_rejected = process_pool(
            input_root=args.open_in,
            output_root=args.open_out,
            source_pool="open",
            dataset_version=dataset_version,
            seen_hashes=seen_hashes,
            rejected_rows=rejected_rows,
            reject_reasons=reject_reasons,
            tech_kept=tech_kept,
            tech_rejected=tech_rejected,
        )

    args.reports_dir.mkdir(parents=True, exist_ok=True)
    rejected_path = args.reports_dir / "phase2_rejected.jsonl"
    with rejected_path.open("w", encoding="utf-8") as handle:
        for row in rejected_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    report = {
        "phase": 2,
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_version": dataset_version,
        "inputs": {
            "closed": _rel(args.closed_in),
            "open": _rel(args.open_in) if include_open else None,
        },
        "outputs": {
            "closed_sanitized": _rel(args.closed_out),
            "open_sanitized": _rel(args.open_out) if include_open else None,
            "rejected_jsonl": _rel(rejected_path),
        },
        "counts": {
            "closed_input": len(_iter_incidents(args.closed_in)),
            "closed_kept": closed_kept,
            "closed_rejected": closed_rejected,
            "open_input": len(_iter_incidents(args.open_in)) if include_open else 0,
            "open_kept": open_kept,
            "open_rejected": open_rejected,
            "total_kept": closed_kept + open_kept,
            "total_rejected": closed_rejected + open_rejected,
            "unique_content_hashes": len(seen_hashes),
        },
        "reject_reasons": dict(reject_reasons.most_common()),
        "kept_by_technology": dict(tech_kept.most_common()),
        "rejected_by_technology": dict(tech_rejected.most_common()),
        "notes": [
            "Sanitized incidents are candidates for Phase 3 knowledge extraction/curation.",
            "Closed pool is preferred for RAG knowledge; open pool is for eval/symptoms.",
            "failure_category values remain heuristic until human curation.",
        ],
    }
    report_path = args.reports_dir / "phase2_clean_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Bump VERSION file when cleaning succeeds.
    VERSION_PATH.write_text("0.2.0-phase2\n", encoding="utf-8")

    print(json.dumps(report["counts"], indent=2))
    print(f"reject_reasons={report['reject_reasons']}")
    print(f"report={_rel(report_path)}")
    print(f"rejected_log={_rel(rejected_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
