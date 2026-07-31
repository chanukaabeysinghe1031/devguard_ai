"""Classify uploaded files into Phase 6A ArtifactKind values."""

from __future__ import annotations

from pathlib import Path

from app.domain.artifacts.enums import ArtifactKind
from app.domain.enums import FileType


def classify_upload(
    *,
    filename: str,
    file_type: FileType,
    content: str | None = None,
) -> ArtifactKind:
    """Map an uploaded file to an artifact kind without inventing content."""
    name = filename.lower()
    suffix = Path(name).suffix

    if file_type == FileType.LOG or suffix in {".log", ".txt"}:
        return ArtifactKind.EXECUTION_LOG
    if file_type == FileType.WORKFLOW_YAML or "workflow" in name or suffix in {".yml", ".yaml"}:
        if "reusable" in name:
            return ArtifactKind.REUSABLE_WORKFLOW_YAML
        return ArtifactKind.WORKFLOW_YAML
    if file_type == FileType.TERRAFORM or suffix in {".tf", ".tfvars"}:
        if suffix == ".tfvars" or "tfvars" in name:
            return ArtifactKind.VARIABLE_FILE
        return ArtifactKind.TERRAFORM_FILE
    if name.endswith(".terraform.lock.hcl") or name.endswith(".lock.hcl"):
        return ArtifactKind.TERRAFORM_LOCK
    if file_type == FileType.JSON or suffix == ".json":
        lowered = (content or "")[:4000].lower()
        if "resource_changes" in lowered or '"format_version"' in lowered:
            return ArtifactKind.TERRAFORM_PLAN_JSON
        if '"statement"' in lowered and ('"effect"' in lowered or '"action"' in lowered):
            return ArtifactKind.IAM_POLICY_JSON
        if "changed_files" in lowered or name.endswith("changed_files.json"):
            return ArtifactKind.CHANGED_FILES_METADATA
        if "accessdenied" in lowered or "errorcode" in lowered:
            return ArtifactKind.AWS_ERROR_METADATA
        return ArtifactKind.OTHER
    return ArtifactKind.OTHER
