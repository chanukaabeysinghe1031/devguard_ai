"""Built-in IAM policy structural verifier (deterministic; no LLM)."""

from __future__ import annotations

import json
from typing import Any

from app.ai.counterfactual_remediation.verification._helpers import (
    artifact_type_str,
    is_iam_family,
    proposed_content,
)
from app.ai.counterfactual_remediation.verification.base import BaseVerifier
from app.domain.counterfactual_remediation.verification_enums import VerifierResultStatus
from app.domain.counterfactual_remediation.verification_models import VerifierResult
from app.domain.counterfactual_remediation.verification_versions import (
    IAM_STRUCTURAL_VERIFIER_VERSION,
)


class IamStructuralVerifier(BaseVerifier):
    """
    Structural IAM checks:
    - JSON parseable
    - Statement Effect required
    - Reject Action/Resource wildcards as FAIL (least-privilege structural gate)
    """

    name = "iam_structural"
    version = IAM_STRUCTURAL_VERIFIER_VERSION

    def supports(self, candidate: Any) -> bool:
        return is_iam_family(artifact_type_str(candidate))

    def execute(self, workspace: Any, candidate: Any) -> VerifierResult:
        content = proposed_content(candidate) or _read_first(workspace)
        if not content.strip():
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="no_iam_content",
                findings=["empty_proposed_fragment"],
            )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="iam_json_invalid",
                findings=[f"json_error:{exc.msg}"],
            )

        findings: list[str] = []
        statements = _extract_statements(parsed)
        if not statements:
            findings.append("no_statement_array")
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="iam_missing_statements",
                findings=findings,
            )

        for idx, stmt in enumerate(statements):
            if not isinstance(stmt, dict):
                findings.append(f"statement_{idx}_not_object")
                continue
            effect = stmt.get("Effect") or stmt.get("effect")
            if effect not in {"Allow", "Deny"}:
                findings.append(f"statement_{idx}_missing_or_invalid_Effect")
            actions = _as_list(stmt.get("Action") or stmt.get("action"))
            resources = _as_list(stmt.get("Resource") or stmt.get("resource"))
            if any(a == "*" for a in actions):
                findings.append(f"statement_{idx}_Action_wildcard")
            if any(r == "*" for r in resources):
                findings.append(f"statement_{idx}_Resource_wildcard")

        if any("wildcard" in f for f in findings) or any(
            "missing_or_invalid_Effect" in f for f in findings
        ):
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="iam_structural_failed",
                findings=findings,
            )
        if findings:
            return self._result(
                status=VerifierResultStatus.WARNING,
                candidate=candidate,
                message="iam_structural_warnings",
                findings=findings,
            )
        return self._result(
            status=VerifierResultStatus.PASS,
            candidate=candidate,
            message="iam_structural_ok",
        )


def _extract_statements(parsed: Any) -> list[Any]:
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        stmt = parsed.get("Statement") or parsed.get("statement")
        if isinstance(stmt, list):
            return stmt
        if isinstance(stmt, dict):
            return [stmt]
        # Inline single statement object
        if "Effect" in parsed or "Action" in parsed:
            return [parsed]
    return []


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _read_first(workspace: Any) -> str:
    root = getattr(workspace, "root", None)
    files = getattr(workspace, "files_written", None) or []
    if root is None or not files:
        return ""
    try:
        return (root / files[0]).read_text(encoding="utf-8")
    except OSError:
        return ""
