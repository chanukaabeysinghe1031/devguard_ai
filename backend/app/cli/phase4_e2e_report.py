"""Write E2E regression markdown/json under /app/_phase4_out."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.ai.classification.hybrid_classifier import HybridClassifier
from app.ai.orchestration.analysis_context import AnalysisContext
from tests.e2e_regression.scenarios import SCENARIOS

OUT = Path("/app/_phase4_out")
OUT.mkdir(parents=True, exist_ok=True)


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
            "- Automated suite asserts classification and failure-state "
            "expectations without paid OpenAI.",
            "- Upload/persistence/ownership covered by API tests.",
            "- Optional live-OpenAI smoke is separate and not required for CI.",
            "",
        ]
    )
    (OUT / "E2E_REGRESSION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "e2e_results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"passed={len(rows) - failed} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
