"""External terraform plan adapter — NEVER apply."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.ai.counterfactual_remediation.verification._helpers import (
    artifact_type_str,
    bound_float,
    flag,
    is_terraform_family,
)
from app.ai.counterfactual_remediation.verification.base import BaseVerifier
from app.ai.counterfactual_remediation.verification.subprocess_runner import run_tool
from app.domain.counterfactual_remediation.verification_enums import VerifierResultStatus
from app.domain.counterfactual_remediation.verification_models import VerifierResult
from app.domain.counterfactual_remediation.verification_versions import (
    TERRAFORM_PLAN_VERIFIER_VERSION,
)


class TerraformPlanVerifier(BaseVerifier):
    """
    Runs `terraform plan -refresh=false -input=false -no-color`.

    Never apply. If init is not possible → UNAVAILABLE.
    """

    name = "terraform_plan"
    version = TERRAFORM_PLAN_VERIFIER_VERSION
    required = False  # plan is supportive; validate is the hard gate for VERIFIED

    def __init__(
        self,
        *,
        enabled: bool = False,
        timeout: float = 60.0,
        max_stdout_chars: int = 20_000,
    ) -> None:
        self._enabled = enabled
        self._timeout = timeout
        self._max_stdout = max_stdout_chars
        self._tool_path = shutil.which("terraform")

    @classmethod
    def from_settings(cls, settings: Any) -> TerraformPlanVerifier:
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
        base.update({"enabled": self._enabled, "tool_path": self._tool_path})
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
        if not (list(root.rglob("*.tf")) or list(root.rglob("*.tf.json"))):
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="no_tf_files_in_workspace",
                tool_path=self._tool_path,
            )

        # Plan requires initialized backend/providers; attempt light init first.
        init_result = run_tool(
            [self._tool_path, "init", "-backend=false", "-input=false", "-no-color"],
            cwd=root,
            timeout=self._timeout,
            max_stdout_chars=self._max_stdout,
        )
        if init_result.timed_out or init_result.returncode != 0:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="terraform_plan_init_unavailable",
                findings=["init_required_for_plan"],
                stdout_excerpt=init_result.stdout,
                stderr_excerpt=init_result.stderr,
                returncode=init_result.returncode,
                duration_ms=init_result.duration_ms,
                tool_path=self._tool_path,
            )

        result = run_tool(
            [
                self._tool_path,
                "plan",
                "-refresh=false",
                "-input=false",
                "-no-color",
                "-lock=false",
            ],
            cwd=root,
            timeout=self._timeout,
            max_stdout_chars=self._max_stdout,
        )
        if result.timed_out:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="terraform_plan_timeout",
                stdout_excerpt=result.stdout,
                stderr_excerpt=result.stderr,
                returncode=result.returncode,
                duration_ms=result.duration_ms,
                tool_path=self._tool_path,
            )
        if result.returncode != 0:
            combined = f"{result.stdout}\n{result.stderr}".lower()
            # Soft warnings for provider/credential gaps vs hard config FAIL.
            if any(
                token in combined
                for token in ("no valid credential", "authorization", "provider", "403", "401")
            ):
                return self._result(
                    status=VerifierResultStatus.WARNING,
                    candidate=candidate,
                    message="terraform_plan_credential_or_provider_warning",
                    findings=["plan_incomplete_without_credentials"],
                    stdout_excerpt=result.stdout,
                    stderr_excerpt=result.stderr,
                    returncode=result.returncode,
                    duration_ms=result.duration_ms,
                    tool_path=self._tool_path,
                )
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="terraform_plan_failed",
                stdout_excerpt=result.stdout,
                stderr_excerpt=result.stderr,
                returncode=result.returncode,
                duration_ms=result.duration_ms,
                tool_path=self._tool_path,
            )
        return self._result(
            status=VerifierResultStatus.PASS,
            candidate=candidate,
            message="terraform_plan_ok",
            stdout_excerpt=result.stdout,
            stderr_excerpt=result.stderr,
            returncode=result.returncode,
            duration_ms=result.duration_ms,
            tool_path=self._tool_path,
        )
