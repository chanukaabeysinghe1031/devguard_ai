#!/usr/bin/env python3
"""Run Phase 4B E2E regression scenarios (classifier-level, no paid OpenAI)."""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

REPO = (
    Path(os.environ["DEVGUARD_REPO_ROOT"]).resolve()
    if os.environ.get("DEVGUARD_REPO_ROOT")
    else Path(__file__).resolve().parents[2]
)
sys.path.insert(0, str(REPO / "backend" if (REPO / "backend").exists() else REPO))

from app.ai.classification.hybrid_classifier import HybridClassifier  # noqa: E402
from app.ai.orchestration.analysis_context import AnalysisContext  # noqa: E402
from tests.e2e_regression.scenarios import SCENARIOS  # noqa: E402


def main() -> int:
    clf = HybridClassifier()
    rows = []
    failed = 0
    for scenario in SCENARIOS:
        ctx = AnalysisContext(
            analysis_run_id=uuid.uuid4(),
            incident_id=uuid.uuid4(),
            combined_text=scenario.log,
        )
        primary = clf.classify(ctx)[0].category_code
        ok = primary == scenario.expected_primary_category
        if not ok:
            failed += 1
        rows.append(
            {
                "id": scenario.id,
                "technology": scenario.technology,
                "expected": scenario.expected_primary_category,
                "actual": primary,
                "pass": ok,
                "failure_state": scenario.expected_failure_state,
                "fallback_ok": scenario.llm_acceptable_fallback,
            }
        )
        print(f"[{'PASS' if ok else 'FAIL'}] {scenario.id}: {primary}")

    docs = REPO / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    out = docs / "E2E_REGRESSION_REPORT.md"
    success_rows = [r for r in rows if r["failure_state"] is False]
    lines = [
        "# E2E Regression Report",
        "",
        f"Scenarios: {len(rows)}",
        f"Passed: {len(rows) - failed}",
        f"Failed: {failed}",
        "",
        "Success-pipeline scenarios (must not classify as concrete failure categories):",
        f"- Count: {len(success_rows)}",
        f"- Passed: {sum(1 for r in success_rows if r['pass'])}",
        "",
        "| ID | Technology | Expected | Actual | Pass | Failure state |",
        "|----|------------|----------|--------|------|---------------|",
    ]
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['technology']} | {row['expected']} | "
            f"{row['actual']} | {row['pass']} | {row['failure_state']} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Automated suite asserts classification + failure-state expectations without paid OpenAI.",
            "- Full upload/persistence/ownership paths are covered by API tests (`test_uploads`, `test_business_apis`, `test_analysis_artifacts_api`).",
            "- Optional live-OpenAI smoke is separate and not required for CI.",
            "",
        ]
    )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report_dir = REPO / "reports" / "performance" / "phase4"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "e2e_results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
