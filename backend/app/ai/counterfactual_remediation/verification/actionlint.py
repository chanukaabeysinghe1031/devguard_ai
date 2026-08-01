"""External actionlint adapter for GitHub Actions workflow YAML."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.ai.counterfactual_remediation.verification._helpers import (
    artifact_type_str,
    bound_float,
    flag,
    is_workflow_family,
)
from app.ai.counterfactual_remediation.verification.base import BaseVerifier
from app.ai.counterfactual_remediation.verification.subprocess_runner import run_tool
from app.domain.counterfactual_remediation.verification_enums import VerifierResultStatus
from app.domain.counterfactual_remediation.verification_models import VerifierResult
from app.domain.counterfactual_remediation.verification_versions import ACTIONLINT_VERIFIER_VERSION


class ActionlintVerifier(BaseVerifier):
    """Runs actionlint on workflow files in the temp workspace."""

    name = "actionlint"
    version = ACTIONLINT_VERIFIER_VERSION

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
        self._tool_path = shutil.which("actionlint")

    @classmethod
    def from_settings(cls, settings: Any) -> ActionlintVerifier:
        return cls(
            enabled=flag(settings, "actionlint_verifier_enabled", False),
            timeout=bound_float(settings, "max_verifier_timeout_seconds", 60.0),
            max_stdout_chars=int(
                getattr(settings, "max_verifier_stdout_chars", 20_000) if settings else 20_000
            ),
        )

    def supports(self, candidate: Any) -> bool:
        return self._enabled and is_workflow_family(artifact_type_str(candidate))

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
                message="actionlint_verifier_disabled",
                tool_path=self._tool_path,
            )
        if not self._tool_path:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="actionlint_binary_missing",
                findings=["binary_not_found:actionlint"],
            )
        root: Path | None = getattr(workspace, "root", None)
        if root is None:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="workspace_missing",
                tool_path=self._tool_path,
            )
        targets = [
            p
            for p in root.rglob("*")
            if p.is_file() and p.suffix.lower() in {".yml", ".yaml"}
        ]
        if not targets:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="no_yaml_workflow_files",
                tool_path=self._tool_path,
            )

        argv = [self._tool_path, *[str(p) for p in targets[:20]]]
        result = run_tool(
            argv,
            cwd=root,
            timeout=self._timeout,
            max_stdout_chars=self._max_stdout,
        )
        if result.timed_out:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="actionlint_timeout",
                stdout_excerpt=result.stdout,
                stderr_excerpt=result.stderr,
                returncode=result.returncode,
                duration_ms=result.duration_ms,
                tool_path=self._tool_path,
            )
        if result.returncode != 0:
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="actionlint_failed",
                findings=["actionlint_reported_issues"],
                stdout_excerpt=result.stdout,
                stderr_excerpt=result.stderr,
                returncode=result.returncode,
                duration_ms=result.duration_ms,
                tool_path=self._tool_path,
            )
        return self._result(
            status=VerifierResultStatus.PASS,
            candidate=candidate,
            message="actionlint_ok",
            stdout_excerpt=result.stdout,
            stderr_excerpt=result.stderr,
            returncode=result.returncode,
            duration_ms=result.duration_ms,
            tool_path=self._tool_path,
        )
