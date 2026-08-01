"""Built-in JSON parse / schema-shape verifier (no LLM)."""

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
from app.domain.counterfactual_remediation.verification_versions import JSON_SCHEMA_VERIFIER_VERSION


class JsonSchemaVerifier(BaseVerifier):
    """Parse-only JSON validator for IAM / JSON policy fragments."""

    name = "json_schema"
    version = JSON_SCHEMA_VERIFIER_VERSION

    def supports(self, candidate: Any) -> bool:
        artifact = artifact_type_str(candidate)
        if is_iam_family(artifact):
            return True
        patch_format = str(getattr(candidate, "patch_format", "") or "").upper()
        return patch_format in {"JSON_FRAGMENT", "IAM_POLICY_JSON"}

    def execute(self, workspace: Any, candidate: Any) -> VerifierResult:
        content = proposed_content(candidate)
        if not content.strip():
            # Try workspace files
            content = _read_first_workspace_text(workspace) or content
        if not content.strip():
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="no_json_content",
                findings=["empty_proposed_fragment"],
            )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="json_parse_failed",
                findings=[f"json_error:{exc.msg}"],
            )
        findings: list[str] = []
        if not isinstance(parsed, (dict, list)):
            findings.append("json_root_not_object_or_array")
            return self._result(
                status=VerifierResultStatus.WARNING,
                candidate=candidate,
                message="json_parsed_non_object",
                findings=findings,
                metadata={"root_type": type(parsed).__name__},
            )
        return self._result(
            status=VerifierResultStatus.PASS,
            candidate=candidate,
            message="json_parsed",
            findings=findings,
            metadata={"root_type": type(parsed).__name__},
        )


def _read_first_workspace_text(workspace: Any) -> str:
    root = getattr(workspace, "root", None)
    files = getattr(workspace, "files_written", None) or []
    if root is None or not files:
        return ""
    try:
        path = root / files[0]
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""
