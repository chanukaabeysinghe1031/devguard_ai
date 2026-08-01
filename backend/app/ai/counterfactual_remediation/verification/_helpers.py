"""Shared helpers for Phase 6A.6 Part 3 verifier adapters."""

from __future__ import annotations

from typing import Any

from app.ai.counterfactual_remediation.safety import mask_for_context
from app.domain.counterfactual_remediation.enums import (
    CounterfactualCandidateStatus,
    RemediationArtifactType,
)
from app.domain.counterfactual_remediation.models import CounterfactualRemediationCandidate


def enum_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value.value if hasattr(value, "value") else value)


def artifact_type_str(candidate: CounterfactualRemediationCandidate | Any) -> str:
    return enum_str(getattr(candidate, "artifact_type", None)).upper()


def is_terraform_family(artifact_type: str) -> bool:
    return artifact_type in {
        RemediationArtifactType.TERRAFORM_CONFIGURATION.value,
        RemediationArtifactType.TERRAFORM_VARIABLES.value,
        RemediationArtifactType.TERRAFORM_POLICY.value,
    }


def is_workflow_family(artifact_type: str) -> bool:
    return artifact_type in {
        RemediationArtifactType.GITHUB_WORKFLOW.value,
        RemediationArtifactType.REUSABLE_WORKFLOW.value,
    }


def is_iam_family(artifact_type: str) -> bool:
    return artifact_type in {
        RemediationArtifactType.IAM_POLICY.value,
        RemediationArtifactType.RESOURCE_POLICY.value,
    }


def is_dependency_family(artifact_type: str) -> bool:
    return artifact_type in {
        RemediationArtifactType.DEPENDENCY_MANIFEST.value,
        RemediationArtifactType.LOCK_FILE.value,
    }


def artifact_family(artifact_type: str) -> str:
    if is_terraform_family(artifact_type):
        return "terraform"
    if is_workflow_family(artifact_type):
        return "workflow"
    if is_iam_family(artifact_type):
        return "iam"
    if is_dependency_family(artifact_type):
        return "dependency"
    if artifact_type in {
        RemediationArtifactType.DOCKERFILE.value,
        RemediationArtifactType.DOCKER_COMPOSE.value,
        RemediationArtifactType.KUBERNETES_MANIFEST.value,
        RemediationArtifactType.APPLICATION_CONFIGURATION.value,
        RemediationArtifactType.ENVIRONMENT_CONFIGURATION.value,
    }:
        return "security"
    return "generic"


def redact_and_truncate(text: str | None, *, max_chars: int = 20_000) -> str:
    """Mask secrets and bound length before persist/log."""
    if not text:
        return ""
    masked = mask_for_context(text)
    if len(masked) <= max_chars:
        return masked
    return masked[: max(0, max_chars - 20)] + "\n...[truncated]..."


def proposed_content(candidate: CounterfactualRemediationCandidate | Any) -> str:
    changes = getattr(candidate, "changes", None) or []
    for change in changes:
        proposed = getattr(change, "proposed_fragment", None)
        if isinstance(proposed, str) and proposed.strip():
            return proposed
        if isinstance(change, dict):
            frag = change.get("proposed_fragment")
            if isinstance(frag, str) and frag.strip():
                return frag
    rendered = getattr(candidate, "rendered_patch", None)
    if isinstance(rendered, str) and rendered.strip():
        return rendered
    return ""


def original_content(candidate: CounterfactualRemediationCandidate | Any) -> str:
    changes = getattr(candidate, "changes", None) or []
    for change in changes:
        original = getattr(change, "original_fragment", None)
        if isinstance(original, str) and original.strip():
            return original
        if isinstance(change, dict):
            frag = change.get("original_fragment")
            if isinstance(frag, str) and frag.strip():
                return frag
    return ""


def candidate_ready_for_verification(candidate: CounterfactualRemediationCandidate | Any) -> bool:
    status = enum_str(getattr(candidate, "status", None))
    if status == CounterfactualCandidateStatus.READY_FOR_VERIFICATION.value:
        return True
    priority = enum_str(getattr(candidate, "priority_status", None))
    if priority in {"PRIORITY_CANDIDATE", "ALTERNATIVE_CANDIDATE"}:
        return bool(proposed_content(candidate) or getattr(candidate, "rendered_patch", None))
    return False


def flag(settings: Any, name: str, default: bool = False) -> bool:
    if settings is None:
        return default
    value = getattr(settings, name, default)
    return bool(value)


def bound_int(settings: Any, name: str, default: int) -> int:
    if settings is None:
        return default
    try:
        return int(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default


def bound_float(settings: Any, name: str, default: float) -> float:
    if settings is None:
        return default
    try:
        return float(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default
