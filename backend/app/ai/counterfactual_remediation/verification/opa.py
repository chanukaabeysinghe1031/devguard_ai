"""External OPA policy adapter."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.ai.counterfactual_remediation.verification._helpers import (
    artifact_type_str,
    bound_float,
    flag,
    is_iam_family,
)
from app.ai.counterfactual_remediation.verification.base import BaseVerifier
from app.ai.counterfactual_remediation.verification.subprocess_runner import run_tool
from app.domain.counterfactual_remediation.verification_enums import VerifierResultStatus
from app.domain.counterfactual_remediation.verification_models import VerifierResult
from app.domain.counterfactual_remediation.verification_versions import OPA_VERIFIER_VERSION


class OpaVerifier(BaseVerifier):
    """
    Runs `opa check` / `opa eval` when a policy input is provided.

    Without policy input or binary → UNAVAILABLE (never fake PASS).
    """

    name = "opa"
    version = OPA_VERIFIER_VERSION
    required = False

    def __init__(
        self,
        *,
        enabled: bool = False,
        timeout: float = 60.0,
        max_stdout_chars: int = 20_000,
        policy_path: str | None = None,
        policy_text: str | None = None,
        eval_query: str | None = None,
    ) -> None:
        self._enabled = enabled
        self._timeout = timeout
        self._max_stdout = max_stdout_chars
        self._policy_path = policy_path
        self._policy_text = policy_text
        self._eval_query = eval_query
        self._tool_path = shutil.which("opa")
        self._written_policy: Path | None = None

    @classmethod
    def from_settings(cls, settings: Any, *, policy_path: str | None = None) -> OpaVerifier:
        return cls(
            enabled=flag(settings, "opa_verifier_enabled", False),
            timeout=bound_float(settings, "max_verifier_timeout_seconds", 60.0),
            max_stdout_chars=int(
                getattr(settings, "max_verifier_stdout_chars", 20_000) if settings else 20_000
            ),
            policy_path=policy_path,
        )

    def supports(self, candidate: Any) -> bool:
        if not self._enabled:
            return False
        return is_iam_family(artifact_type_str(candidate)) or bool(
            self._policy_path or self._policy_text
        )

    def is_available(self) -> bool:
        return bool(self._enabled and self._tool_path and (self._policy_path or self._policy_text))

    def health(self) -> dict[str, Any]:
        base = super().health()
        base.update(
            {
                "enabled": self._enabled,
                "tool_path": self._tool_path,
                "has_policy": bool(self._policy_path or self._policy_text),
            }
        )
        return base

    def prepare(self, workspace: Any, candidate: Any) -> None:
        self._written_policy = None
        if not self._policy_text:
            return
        root = getattr(workspace, "root", None)
        if root is None:
            return
        path = Path(root) / ".devguard_opa_policy.rego"
        try:
            path.write_text(self._policy_text, encoding="utf-8")
            self._written_policy = path
        except OSError:
            self._written_policy = None

    def cleanup(self) -> None:
        self._written_policy = None

    def execute(self, workspace: Any, candidate: Any) -> VerifierResult:
        if not self._enabled:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="opa_verifier_disabled",
                tool_path=self._tool_path,
            )
        if not self._tool_path:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="opa_binary_missing",
                findings=["binary_not_found:opa"],
            )
        policy = self._resolve_policy(workspace)
        if policy is None:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="opa_no_policy_input",
                findings=["policy_required"],
                tool_path=self._tool_path,
            )
        root: Path | None = getattr(workspace, "root", None)
        if root is None:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="workspace_missing",
                tool_path=self._tool_path,
            )

        if self._eval_query:
            files = getattr(workspace, "files_written", None) or []
            input_file = str(root / files[0]) if files else str(root)
            argv = [
                self._tool_path,
                "eval",
                "-d",
                str(policy),
                "-i",
                input_file,
                self._eval_query,
            ]
        else:
            argv = [self._tool_path, "check", str(policy)]

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
                message="opa_timeout",
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
                message="opa_failed",
                findings=["opa_reported_issues"],
                stdout_excerpt=result.stdout,
                stderr_excerpt=result.stderr,
                returncode=result.returncode,
                duration_ms=result.duration_ms,
                tool_path=self._tool_path,
            )
        return self._result(
            status=VerifierResultStatus.PASS,
            candidate=candidate,
            message="opa_ok",
            stdout_excerpt=result.stdout,
            stderr_excerpt=result.stderr,
            returncode=result.returncode,
            duration_ms=result.duration_ms,
            tool_path=self._tool_path,
        )

    def _resolve_policy(self, workspace: Any) -> Path | None:
        if self._written_policy and self._written_policy.is_file():
            return self._written_policy
        if self._policy_path:
            path = Path(self._policy_path)
            if path.is_file():
                return path
        return None
