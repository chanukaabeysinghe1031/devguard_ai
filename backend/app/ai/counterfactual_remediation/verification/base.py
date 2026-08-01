"""Verifier adapter protocol / base for Phase 6A.6 Part 3."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from app.domain.counterfactual_remediation.models import CounterfactualRemediationCandidate
from app.domain.counterfactual_remediation.verification_models import VerifierResult


@runtime_checkable
class Verifier(Protocol):
    """Independent, deterministic verifier — LLMs are never verifiers."""

    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    def supports(self, candidate: CounterfactualRemediationCandidate | Any) -> bool: ...

    def is_available(self) -> bool: ...

    def prepare(
        self,
        workspace: Any,
        candidate: CounterfactualRemediationCandidate | Any,
    ) -> None: ...

    def execute(
        self,
        workspace: Any,
        candidate: CounterfactualRemediationCandidate | Any,
    ) -> VerifierResult: ...

    def cleanup(self) -> None: ...

    def health(self) -> dict[str, Any]: ...


class BaseVerifier(ABC):
    """Shared adapter skeleton with soft-fail defaults."""

    name: str = "base"
    version: str = "base_v0"
    required: bool = True

    def supports(self, candidate: CounterfactualRemediationCandidate | Any) -> bool:
        return False

    def is_available(self) -> bool:
        return True

    def prepare(
        self,
        workspace: Any,
        candidate: CounterfactualRemediationCandidate | Any,
    ) -> None:
        return None

    @abstractmethod
    def execute(
        self,
        workspace: Any,
        candidate: CounterfactualRemediationCandidate | Any,
    ) -> VerifierResult: ...

    def cleanup(self) -> None:
        return None

    def health(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "available": self.is_available(),
            "required": self.required,
            "llm_verifier": False,
        }

    def _result(
        self,
        *,
        status: Any,
        candidate: CounterfactualRemediationCandidate | Any,
        message: str = "",
        findings: list[str] | None = None,
        stdout_excerpt: str | None = None,
        stderr_excerpt: str | None = None,
        returncode: int | None = None,
        duration_ms: float | None = None,
        tool_path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> VerifierResult:
        return VerifierResult(
            verifier_name=self.name,
            verifier_version=self.version,
            status=status,
            candidate_id=getattr(candidate, "id", None),
            required=self.required,
            message=message,
            findings=list(findings or []),
            stdout_excerpt=stdout_excerpt,
            stderr_excerpt=stderr_excerpt,
            returncode=returncode,
            duration_ms=duration_ms,
            tool_path=tool_path,
            metadata=dict(metadata or {}),
        )
