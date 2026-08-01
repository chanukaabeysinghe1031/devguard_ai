"""External checkov IaC security adapter."""

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
from app.domain.counterfactual_remediation.verification_versions import CHECKOV_VERIFIER_VERSION


class CheckovVerifier(BaseVerifier):
    """Runs `checkov -f <file> --quiet` or directory scan. Missing → UNAVAILABLE."""

    name = "checkov"
    version = CHECKOV_VERIFIER_VERSION
    required = False

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
        self._tool_path = shutil.which("checkov")

    @classmethod
    def from_settings(cls, settings: Any) -> CheckovVerifier:
        return cls(
            enabled=flag(settings, "checkov_verifier_enabled", False),
            timeout=bound_float(settings, "max_verifier_timeout_seconds", 60.0),
            max_stdout_chars=int(
                getattr(settings, "max_verifier_stdout_chars", 20_000) if settings else 20_000
            ),
        )

    def supports(self, candidate: Any) -> bool:
        if not self._enabled:
            return False
        # Primarily terraform / IaC; also useful for k8s/dockerfile families.
        artifact = artifact_type_str(candidate)
        return is_terraform_family(artifact) or artifact in {
            "KUBERNETES_MANIFEST",
            "DOCKERFILE",
            "DOCKER_COMPOSE",
        }

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
                message="checkov_verifier_disabled",
                tool_path=self._tool_path,
            )
        if not self._tool_path:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="checkov_binary_missing",
                findings=["binary_not_found:checkov"],
            )
        root: Path | None = getattr(workspace, "root", None)
        if root is None:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="workspace_missing",
                tool_path=self._tool_path,
            )
        files = getattr(workspace, "files_written", None) or []
        if len(files) == 1:
            argv = [self._tool_path, "-f", str(root / files[0]), "--quiet"]
        else:
            argv = [self._tool_path, "-d", str(root), "--quiet"]

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
                message="checkov_timeout",
                stdout_excerpt=result.stdout,
                stderr_excerpt=result.stderr,
                returncode=result.returncode,
                duration_ms=result.duration_ms,
                tool_path=self._tool_path,
            )
        # checkov exit: 0 = pass, non-zero = findings (treat as FAIL/WARNING).
        if result.returncode == 0:
            return self._result(
                status=VerifierResultStatus.PASS,
                candidate=candidate,
                message="checkov_ok",
                stdout_excerpt=result.stdout,
                stderr_excerpt=result.stderr,
                returncode=result.returncode,
                duration_ms=result.duration_ms,
                tool_path=self._tool_path,
            )
        # Soft WARNING when only informational noise; otherwise FAIL.
        status = VerifierResultStatus.FAIL
        if "Passed checks" in (result.stdout or "") and "Failed checks: 0" in (result.stdout or ""):
            status = VerifierResultStatus.WARNING
        return self._result(
            status=status,
            candidate=candidate,
            message="checkov_findings",
            findings=["checkov_reported_issues"],
            stdout_excerpt=result.stdout,
            stderr_excerpt=result.stderr,
            returncode=result.returncode,
            duration_ms=result.duration_ms,
            tool_path=self._tool_path,
        )
