"""Unit tests for the human-gold retrieval benchmark helpers."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _candidate in (
    Path(__file__).resolve().parents[2],
    Path(__file__).resolve().parents[1].parent,
    Path("/workspace"),
):
    if (_candidate / "scripts" / "dataset" / "benchmark").exists():
        REPO_ROOT = _candidate
        break
SCRIPT_DIR = REPO_ROOT / "scripts" / "dataset" / "benchmark"
if not SCRIPT_DIR.exists():
    import pytest

    pytest.skip("benchmark scripts not mounted in this environment", allow_module_level=True)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_queries import write_assets  # noqa: E402
from metrics import (  # noqa: E402
    average_precision,
    hit_rate,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from retrieve_candidates import propose_relevance  # noqa: E402


def test_generate_queries_writes_expected_counts(tmp_path: Path, monkeypatch) -> None:
    import generate_queries as gq

    monkeypatch.setattr(gq, "BENCH", tmp_path)
    meta = gq.write_assets()
    assert meta["query_count"] >= 120
    queries = list(csv.DictReader((tmp_path / "queries.csv").open(encoding="utf-8")))
    assert len(queries) == meta["query_count"]
    assert len({q["query_id"] for q in queries}) == len(queries)
    assert (tmp_path / "categories.csv").exists()
    assert (tmp_path / "benchmark_metadata.json").exists()
    assert (tmp_path / "evaluation_config.json").exists()


def test_ir_metrics_basic() -> None:
    binary = [0, 1, 1, 0, 0]
    assert precision_at_k(binary, 1) == 0.0
    assert precision_at_k(binary, 3) == 2 / 3
    assert reciprocal_rank(binary) == 0.5
    assert hit_rate(binary, 5) == 1.0
    relevant = {"a", "b"}
    assert recall_at_k(["x", "a", "b"], relevant, 5) == 1.0
    assert average_precision(["a", "x", "b"], relevant) > 0
    assert ndcg_at_k([3, 0, 2], [3, 2, 1], 3) > 0


def test_propose_relevance_is_heuristic_only() -> None:
    query = {
        "query_text": "AWS AccessDenied during deployment",
        "expected_technologies": "aws",
        "failure_category": "aws_permission_failure",
    }
    grade = propose_relevance(
        query,
        {"technology": "aws", "failure_category": "aws_permission_failure"},
        "AccessDenied IAM permission policy missing Allow",
    )
    assert grade >= 2


def test_benchmark_assets_exist_after_generation() -> None:
    # Idempotent regeneration against real benchmark path is acceptable in unit scope
    # only if files already exist from pipeline; assert schema columns if present.
    path = REPO_ROOT / "datasets" / "benchmark" / "queries.csv"
    if not path.exists():
        write_assets()
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert len(rows) >= 120
    required = {
        "query_id",
        "query_text",
        "technology",
        "failure_category",
        "pipeline_stage",
        "difficulty",
        "category_group",
    }
    assert required.issubset(rows[0].keys())
