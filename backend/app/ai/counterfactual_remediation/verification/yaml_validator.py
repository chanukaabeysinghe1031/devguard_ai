"""Built-in YAML parse verifier for workflow fragments (no LLM)."""

from __future__ import annotations

from typing import Any

from app.ai.counterfactual_remediation.verification._helpers import (
    artifact_type_str,
    is_workflow_family,
    proposed_content,
)
from app.ai.counterfactual_remediation.verification.base import BaseVerifier
from app.domain.counterfactual_remediation.verification_enums import VerifierResultStatus
from app.domain.counterfactual_remediation.verification_models import VerifierResult
from app.domain.counterfactual_remediation.verification_versions import YAML_VALIDATOR_VERSION


class YamlValidatorVerifier(BaseVerifier):
    """Parse-only YAML validator. Missing PyYAML → UNAVAILABLE (never fake PASS)."""

    name = "yaml_validator"
    version = YAML_VALIDATOR_VERSION

    def supports(self, candidate: Any) -> bool:
        artifact = artifact_type_str(candidate)
        if is_workflow_family(artifact):
            return True
        patch_format = str(getattr(candidate, "patch_format", "") or "").upper()
        return patch_format in {"YAML_FRAGMENT"}

    def is_available(self) -> bool:
        try:
            import yaml  # noqa: F401
        except ImportError:
            return False
        return True

    def execute(self, workspace: Any, candidate: Any) -> VerifierResult:
        if not self.is_available():
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="pyyaml_not_installed",
                findings=["yaml_library_missing"],
            )
        import yaml

        content = proposed_content(candidate) or _read_first(workspace)
        if not content.strip():
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="no_yaml_content",
                findings=["empty_proposed_fragment"],
            )
        try:
            parsed = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="yaml_parse_failed",
                findings=[f"yaml_error:{type(exc).__name__}"],
            )
        if parsed is None:
            return self._result(
                status=VerifierResultStatus.WARNING,
                candidate=candidate,
                message="yaml_empty_document",
            )
        findings: list[str] = []
        if (
            is_workflow_family(artifact_type_str(candidate))
            and isinstance(parsed, dict)
            and "jobs" not in parsed
            and "on" not in parsed
        ):
            findings.append("workflow_missing_jobs_or_on")
        status = VerifierResultStatus.WARNING if findings else VerifierResultStatus.PASS
        return self._result(
            status=status,
            candidate=candidate,
            message="yaml_parsed",
            findings=findings,
        )


def _read_first(workspace: Any) -> str:
    root = getattr(workspace, "root", None)
    files = getattr(workspace, "files_written", None) or []
    if root is None or not files:
        return ""
    try:
        return (root / files[0]).read_text(encoding="utf-8")
    except OSError:
        return ""
