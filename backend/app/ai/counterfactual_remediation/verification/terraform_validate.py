"""External terraform validate adapter — never apply."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.ai.counterfactual_remediation.verification._helpers import (
    artifact_type_str,
    bound_float,
    flag,
    is_terraform_family,
    redact_and_truncate,
)
from app.ai.counterfactual_remediation.verification.base import BaseVerifier
from app.ai.counterfactual_remediation.verification.subprocess_runner import run_tool
from app.domain.counterfactual_remediation.verification_enums import VerifierResultStatus
from app.domain.counterfactual_remediation.verification_models import VerifierResult
from app.domain.counterfactual_remediation.verification_versions import (
    TERRAFORM_VALIDATE_VERIFIER_VERSION,
)


class TerraformValidateVerifier(BaseVerifier):
    """
    Runs `terraform validate` in the temp workspace.

    Optional light `terraform init -backend=false`. Never apply.
    Missing binary or flag OFF → UNAVAILABLE (never fake PASS).
    """

    name = "terraform_validate"
    version = TERRAFORM_VALIDATE_VERIFIER_VERSION

    def __init__(
        self,
        *,
        enabled: bool = False,
        timeout: float = 60.0,
        max_stdout_chars: int = 20_000,
        attempt_init: bool = True,
    ) -> None:
        self._enabled = enabled
        self._timeout = timeout
        self._max_stdout = max_stdout_chars
        self._attempt_init = attempt_init
        self._tool_path = shutil.which("terraform")

    @classmethod
    def from_settings(cls, settings: Any) -> TerraformValidateVerifier:
        return cls(
            enabled=flag(settings, "terraform_verifier_enabled", False),
            timeout=bound_float(settings, "max_verifier_timeout_seconds", 60.0),
            max_stdout_chars=int(
                getattr(settings, "max_verifier_stdout_chars", 20_000) if settings else 20_000
            ),
        )

    def supports(self, candidate: Any) -> bool:
        return self._enabled and is_terraform_family(artifact_type_str(candidate))

    def is_available(self) -> bool:
        return bool(self._enabled and self._tool_path)

    def health(self) -> dict[str, Any]:
        base = super().health()
        base.update(
            {
                "enabled": self._enabled,
                "tool_path": self._tool_path,
            }
        )
        return base

    def execute(self, workspace: Any, candidate: Any) -> VerifierResult:
        if not self._enabled:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="terraform_verifier_disabled",
                tool_path=self._tool_path,
            )
        if not self._tool_path:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="terraform_binary_missing",
                findings=["binary_not_found:terraform"],
            )
        root: Path | None = getattr(workspace, "root", None)
        if root is None:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="workspace_missing",
                tool_path=self._tool_path,
            )
        tf_files = list(root.rglob("*.tf")) + list(root.rglob("*.tf.json"))
        if not tf_files:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="no_tf_files_in_workspace",
                tool_path=self._tool_path,
                findings=["no_terraform_files"],
            )

        # Optional light init; on failure continue to validate-only when possible.
        init_warning: str | None = None
        if self._attempt_init:
            init_result = run_tool(
                [self._tool_path, "init", "-backend=false", "-input=false", "-no-color"],
                cwd=root,
                timeout=self._timeout,
                max_stdout_chars=self._max_stdout,
            )
            if init_result.timed_out:
                return self._result(
                    status=VerifierResultStatus.UNAVAILABLE,
                    candidate=candidate,
                    message="terraform_init_timeout",
                    stdout_excerpt=init_result.stdout,
                    stderr_excerpt=init_result.stderr,
                    returncode=init_result.returncode,
                    duration_ms=init_result.duration_ms,
                    tool_path=self._tool_path,
                )
            if init_result.returncode != 0:
                init_warning = "terraform_init_failed_validate_only"

        result = run_tool(
            [self._tool_path, "validate", "-no-color"],
            cwd=root,
            timeout=self._timeout,
            max_stdout_chars=self._max_stdout,
        )
        findings: list[str] = []
        if init_warning:
            findings.append(init_warning)
        if result.timed_out:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="terraform_validate_timeout",
                findings=findings,
                stdout_excerpt=result.stdout,
                stderr_excerpt=result.stderr,
                returncode=result.returncode,
                duration_ms=result.duration_ms,
                tool_path=self._tool_path,
            )
        if result.returncode != 0:
            # Distinguishing "needs init" from real FAIL.
            combined = f"{result.stdout}\n{result.stderr}".lower()
            if "initialization" in combined or "terraform init" in combined:
                return self._result(
                    status=VerifierResultStatus.UNAVAILABLE,
                    candidate=candidate,
                    message="terraform_validate_requires_init",
                    findings=findings + ["validate_requires_init"],
                    stdout_excerpt=redact_and_truncate(result.stdout, max_chars=self._max_stdout),
                    stderr_excerpt=redact_and_truncate(result.stderr, max_chars=self._max_stdout),
                    returncode=result.returncode,
                    duration_ms=result.duration_ms,
                    tool_path=self._tool_path,
                )
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="terraform_validate_failed",
                findings=findings,
                stdout_excerpt=result.stdout,
                stderr_excerpt=result.stderr,
                returncode=result.returncode,
                duration_ms=result.duration_ms,
                tool_path=self._tool_path,
            )
        status = VerifierResultStatus.WARNING if findings else VerifierResultStatus.PASS
        return self._result(
            status=status,
            candidate=candidate,
            message="terraform_validate_ok",
            findings=findings,
            stdout_excerpt=result.stdout,
            stderr_excerpt=result.stderr,
            returncode=result.returncode,
            duration_ms=result.duration_ms,
            tool_path=self._tool_path,
        )
