"""Soft-fail GitHub artifact acquisition for Phase 6A.1 (read-only)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.ai.artifacts.bundle_service import mask_artifact_text
from app.core.config import Settings
from app.domain.artifacts.enums import (
    AcquisitionStatus,
    ArtifactKind,
    ArtifactSource,
)
from app.domain.artifacts.models import AcquisitionError, ArtifactRecord, content_sha256
from app.domain.exceptions.integration import GitHubProviderError
from app.domain.interfaces.github_provider import GitHubProvider, GitHubWorkflowRunInfo

logger = structlog.get_logger(__name__)


@dataclass
class GitHubAcquisitionResult:
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    errors: list[AcquisitionError] = field(default_factory=list)
    available: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)


class GitHubArtifactAcquisition:
    """Collects optional analysis artifacts without failing the parent ingestion."""

    EXPECTED_KINDS = (
        ArtifactKind.WORKFLOW_YAML,
        ArtifactKind.COMMIT_METADATA,
        ArtifactKind.CHANGED_FILES_METADATA,
        ArtifactKind.PREVIOUS_SUCCESS_LOG,
    )

    def __init__(self, provider: GitHubProvider, settings: Settings) -> None:
        self._provider = provider
        self._settings = settings

    def enabled(self) -> bool:
        return bool(self._settings.github_artifact_acquisition_enabled)

    async def collect(
        self,
        *,
        installation_id: int,
        repository_full_name: str,
        run: dict[str, Any],
        failed_log_present: bool = False,
    ) -> GitHubAcquisitionResult:
        result = GitHubAcquisitionResult(
            context={
                "provider": "github",
                "repository": repository_full_name,
                "commit_sha": run.get("head_sha"),
                "branch": run.get("head_branch"),
                "workflow_name": run.get("name"),
                "workflow_run_id": run.get("id"),
                "workflow_run_attempt": run.get("run_attempt"),
            }
        )
        if failed_log_present:
            result.available.append(ArtifactKind.EXECUTION_LOG.value)

        if not self.enabled():
            result.missing.extend(k.value for k in self.EXPECTED_KINDS)
            result.errors.append(
                AcquisitionError(
                    artifact_kind="github_acquisition",
                    code="disabled",
                    message="GITHUB_ARTIFACT_ACQUISITION_ENABLED is false",
                )
            )
            return result

        workflow_id = run.get("workflow_id")
        head_sha = run.get("head_sha")
        head_branch = run.get("head_branch")
        failed_run_id = run.get("id")

        await self._collect_workflow_yaml(
            result,
            installation_id=installation_id,
            repository_full_name=repository_full_name,
            workflow_id=int(workflow_id) if workflow_id is not None else None,
            head_sha=str(head_sha) if head_sha else None,
        )
        await self._collect_commit_metadata(
            result,
            installation_id=installation_id,
            repository_full_name=repository_full_name,
            head_sha=str(head_sha) if head_sha else None,
        )
        await self._collect_changed_files(
            result,
            installation_id=installation_id,
            repository_full_name=repository_full_name,
            head_sha=str(head_sha) if head_sha else None,
        )
        await self._collect_previous_success(
            result,
            installation_id=installation_id,
            repository_full_name=repository_full_name,
            workflow_id=int(workflow_id) if workflow_id is not None else None,
            branch=str(head_branch) if head_branch else None,
            failed_run_id=int(failed_run_id) if failed_run_id is not None else None,
        )

        # Explicit workflow-run metadata snapshot (always derived when enabled).
        actor_login = run.get("actor_login")
        if not actor_login and isinstance(run.get("actor"), dict):
            actor_login = (run.get("actor") or {}).get("login")
        meta = {
            "run_id": failed_run_id,
            "name": run.get("name"),
            "conclusion": run.get("conclusion"),
            "status": run.get("status"),
            "head_branch": head_branch,
            "head_sha": head_sha,
            "html_url": run.get("html_url"),
            "actor_login": actor_login,
            "run_attempt": run.get("run_attempt"),
            "event": run.get("event"),
        }
        content = json.dumps(meta, indent=2, default=str)
        masked, redaction = mask_artifact_text(content)
        result.artifacts.append(
            ArtifactRecord(
                id=str(uuid.uuid4()),
                kind=ArtifactKind.OTHER,
                source=ArtifactSource.GITHUB,
                filename="workflow_run_metadata.json",
                content_hash=content_sha256(masked),
                content=masked,
                acquisition_status=AcquisitionStatus.COLLECTED,
                redaction_status=redaction,
                metadata={"role": "workflow_run_metadata"},
            )
        )
        result.available.append("workflow_run_metadata")

        present = {a.kind for a in result.artifacts}
        for kind in self.EXPECTED_KINDS:
            if kind not in present and kind.value not in result.missing:
                result.missing.append(kind.value)

        result.available = sorted(set(result.available))
        result.missing = sorted(set(result.missing))
        return result

    async def _collect_workflow_yaml(
        self,
        result: GitHubAcquisitionResult,
        *,
        installation_id: int,
        repository_full_name: str,
        workflow_id: int | None,
        head_sha: str | None,
    ) -> None:
        if not head_sha:
            result.missing.append(ArtifactKind.WORKFLOW_YAML.value)
            result.errors.append(
                AcquisitionError(
                    artifact_kind=ArtifactKind.WORKFLOW_YAML,
                    code="missing_head_sha",
                    message="Cannot fetch workflow YAML without head_sha",
                )
            )
            return
        path: str | None = None
        try:
            workflows = await self._provider.list_repository_workflows(
                installation_id=installation_id,
                repository_full_name=repository_full_name,
            )
            for wf in workflows:
                if workflow_id is not None and wf.workflow_id == workflow_id:
                    path = wf.path
                    break
            if path is None and workflows:
                path = workflows[0].path
        except GitHubProviderError as exc:
            result.errors.append(
                AcquisitionError(
                    artifact_kind=ArtifactKind.WORKFLOW_YAML,
                    code=exc.error_code or "workflow_list_failed",
                    message=exc.message[:500],
                )
            )
            result.missing.append(ArtifactKind.WORKFLOW_YAML.value)
            return

        if not path:
            result.missing.append(ArtifactKind.WORKFLOW_YAML.value)
            result.errors.append(
                AcquisitionError(
                    artifact_kind=ArtifactKind.WORKFLOW_YAML,
                    code="workflow_path_unknown",
                    message="No workflow path available for this run",
                )
            )
            return

        try:
            content = await self._provider.get_repository_file_content(
                installation_id=installation_id,
                repository_full_name=repository_full_name,
                path=path,
                ref=head_sha,
            )
        except GitHubProviderError as exc:
            result.errors.append(
                AcquisitionError(
                    artifact_kind=ArtifactKind.WORKFLOW_YAML,
                    code=exc.error_code or "workflow_yaml_fetch_failed",
                    message=exc.message[:500],
                )
            )
            result.missing.append(ArtifactKind.WORKFLOW_YAML.value)
            return

        if not content:
            result.missing.append(ArtifactKind.WORKFLOW_YAML.value)
            result.errors.append(
                AcquisitionError(
                    artifact_kind=ArtifactKind.WORKFLOW_YAML,
                    code="workflow_yaml_unavailable",
                    message=f"Contents API returned no file for {path}@{head_sha}",
                )
            )
            return

        masked, redaction = mask_artifact_text(content)
        result.artifacts.append(
            ArtifactRecord(
                id=str(uuid.uuid4()),
                kind=ArtifactKind.WORKFLOW_YAML,
                source=ArtifactSource.GITHUB,
                filename=path.split("/")[-1],
                content_hash=content_sha256(masked),
                content=masked,
                acquisition_status=AcquisitionStatus.COLLECTED,
                redaction_status=redaction,
                source_uri=f"github://{repository_full_name}/{path}@{head_sha}",
                metadata={"path": path, "ref": head_sha},
            )
        )
        result.available.append(ArtifactKind.WORKFLOW_YAML.value)

    async def _collect_commit_metadata(
        self,
        result: GitHubAcquisitionResult,
        *,
        installation_id: int,
        repository_full_name: str,
        head_sha: str | None,
    ) -> None:
        if not head_sha:
            result.missing.append(ArtifactKind.COMMIT_METADATA.value)
            return
        try:
            commit = await self._provider.get_commit(
                installation_id=installation_id,
                repository_full_name=repository_full_name,
                sha=head_sha,
            )
        except GitHubProviderError as exc:
            result.errors.append(
                AcquisitionError(
                    artifact_kind=ArtifactKind.COMMIT_METADATA,
                    code=exc.error_code or "commit_fetch_failed",
                    message=exc.message[:500],
                )
            )
            result.missing.append(ArtifactKind.COMMIT_METADATA.value)
            return
        if commit is None:
            result.missing.append(ArtifactKind.COMMIT_METADATA.value)
            result.errors.append(
                AcquisitionError(
                    artifact_kind=ArtifactKind.COMMIT_METADATA,
                    code="commit_unavailable",
                    message=f"Commit {head_sha} not found",
                )
            )
            return
        payload = {
            "sha": commit.sha,
            "message": commit.message,
            "author_login": commit.author_login,
            "html_url": commit.html_url,
            "parents": list(commit.parents),
        }
        content = json.dumps(payload, indent=2)
        masked, redaction = mask_artifact_text(content)
        result.artifacts.append(
            ArtifactRecord(
                id=str(uuid.uuid4()),
                kind=ArtifactKind.COMMIT_METADATA,
                source=ArtifactSource.GITHUB,
                filename="commit_metadata.json",
                content_hash=content_sha256(masked),
                content=masked,
                acquisition_status=AcquisitionStatus.COLLECTED,
                redaction_status=redaction,
                source_uri=commit.html_url,
                metadata={"sha": commit.sha},
            )
        )
        result.available.append(ArtifactKind.COMMIT_METADATA.value)
        if commit.parents:
            result.context["parent_sha"] = commit.parents[0]

    async def _collect_changed_files(
        self,
        result: GitHubAcquisitionResult,
        *,
        installation_id: int,
        repository_full_name: str,
        head_sha: str | None,
    ) -> None:
        parent = result.context.get("parent_sha")
        if not head_sha or not parent:
            # Attempt parent from commit collection; if absent, mark missing.
            if ArtifactKind.COMMIT_METADATA.value not in result.available:
                result.missing.append(ArtifactKind.CHANGED_FILES_METADATA.value)
                return
            result.missing.append(ArtifactKind.CHANGED_FILES_METADATA.value)
            result.errors.append(
                AcquisitionError(
                    artifact_kind=ArtifactKind.CHANGED_FILES_METADATA,
                    code="no_parent_commit",
                    message="Cannot compare changed files without a parent commit",
                )
            )
            return
        try:
            compare = await self._provider.compare_commits(
                installation_id=installation_id,
                repository_full_name=repository_full_name,
                base=str(parent),
                head=head_sha,
            )
        except GitHubProviderError as exc:
            result.errors.append(
                AcquisitionError(
                    artifact_kind=ArtifactKind.CHANGED_FILES_METADATA,
                    code=exc.error_code or "compare_failed",
                    message=exc.message[:500],
                )
            )
            result.missing.append(ArtifactKind.CHANGED_FILES_METADATA.value)
            return
        if compare is None:
            result.missing.append(ArtifactKind.CHANGED_FILES_METADATA.value)
            return
        payload = {
            "base_sha": compare.base_sha,
            "head_sha": compare.head_sha,
            "status": compare.status,
            "ahead_by": compare.ahead_by,
            "behind_by": compare.behind_by,
            "total_commits": compare.total_commits,
            "changed_files": [
                {
                    "filename": f.filename,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "changes": f.changes,
                    "previous_filename": f.previous_filename,
                }
                for f in compare.files
            ],
        }
        content = json.dumps(payload, indent=2)
        masked, redaction = mask_artifact_text(content)
        result.artifacts.append(
            ArtifactRecord(
                id=str(uuid.uuid4()),
                kind=ArtifactKind.CHANGED_FILES_METADATA,
                source=ArtifactSource.GITHUB,
                filename="changed_files.json",
                content_hash=content_sha256(masked),
                content=masked,
                acquisition_status=AcquisitionStatus.COLLECTED,
                redaction_status=redaction,
                metadata={"file_count": len(compare.files)},
            )
        )
        result.available.append(ArtifactKind.CHANGED_FILES_METADATA.value)

    async def _collect_previous_success(
        self,
        result: GitHubAcquisitionResult,
        *,
        installation_id: int,
        repository_full_name: str,
        workflow_id: int | None,
        branch: str | None,
        failed_run_id: int | None,
    ) -> None:
        try:
            runs = await self._provider.list_workflow_runs(
                installation_id=installation_id,
                repository_full_name=repository_full_name,
                workflow_id=workflow_id,
                branch=branch,
                status="completed",
                per_page=20,
            )
        except GitHubProviderError as exc:
            result.errors.append(
                AcquisitionError(
                    artifact_kind=ArtifactKind.PREVIOUS_SUCCESS_LOG,
                    code=exc.error_code or "list_runs_failed",
                    message=exc.message[:500],
                )
            )
            result.missing.append(ArtifactKind.PREVIOUS_SUCCESS_LOG.value)
            result.missing.append("previous_successful_run_metadata")
            return

        previous: GitHubWorkflowRunInfo | None = None
        for candidate in runs:
            if failed_run_id is not None and candidate.run_id == failed_run_id:
                continue
            if candidate.conclusion == "success":
                previous = candidate
                break

        if previous is None:
            result.missing.append(ArtifactKind.PREVIOUS_SUCCESS_LOG.value)
            result.missing.append("previous_successful_run_metadata")
            result.errors.append(
                AcquisitionError(
                    artifact_kind=ArtifactKind.PREVIOUS_SUCCESS_LOG,
                    code="no_previous_success",
                    message="No prior successful workflow run found",
                )
            )
            return

        meta = {
            "run_id": previous.run_id,
            "name": previous.name,
            "conclusion": previous.conclusion,
            "head_sha": previous.head_sha,
            "head_branch": previous.head_branch,
            "html_url": previous.html_url,
            "run_number": previous.run_number,
        }
        content = json.dumps(meta, indent=2, default=str)
        masked, redaction = mask_artifact_text(content)
        result.artifacts.append(
            ArtifactRecord(
                id=str(uuid.uuid4()),
                kind=ArtifactKind.OTHER,
                source=ArtifactSource.GITHUB,
                filename="previous_successful_run_metadata.json",
                content_hash=content_sha256(masked),
                content=masked,
                acquisition_status=AcquisitionStatus.COLLECTED,
                redaction_status=redaction,
                metadata={"role": "previous_successful_run_metadata", "run_id": previous.run_id},
            )
        )
        result.available.append("previous_successful_run_metadata")

        try:
            archive = await self._provider.download_workflow_run_logs(
                installation_id=installation_id,
                repository_full_name=repository_full_name,
                run_id=previous.run_id,
            )
        except GitHubProviderError as exc:
            result.errors.append(
                AcquisitionError(
                    artifact_kind=ArtifactKind.PREVIOUS_SUCCESS_LOG,
                    code=exc.error_code or "previous_logs_failed",
                    message=exc.message[:500],
                )
            )
            result.missing.append(ArtifactKind.PREVIOUS_SUCCESS_LOG.value)
            return

        if not archive:
            result.missing.append(ArtifactKind.PREVIOUS_SUCCESS_LOG.value)
            result.errors.append(
                AcquisitionError(
                    artifact_kind=ArtifactKind.PREVIOUS_SUCCESS_LOG,
                    code="previous_logs_unavailable",
                    message="Previous successful run logs not available",
                )
            )
            return

        extracted = _first_text_from_log_archive(archive)
        if extracted is None:
            result.missing.append(ArtifactKind.PREVIOUS_SUCCESS_LOG.value)
            result.errors.append(
                AcquisitionError(
                    artifact_kind=ArtifactKind.PREVIOUS_SUCCESS_LOG,
                    code="previous_log_extract_failed",
                    message="Could not extract a text log from the previous-success archive",
                )
            )
            return

        name, text = extracted
        text = text[: self._settings.artifact_max_content_chars]
        masked, redaction = mask_artifact_text(text)
        result.artifacts.append(
            ArtifactRecord(
                id=str(uuid.uuid4()),
                kind=ArtifactKind.PREVIOUS_SUCCESS_LOG,
                source=ArtifactSource.GITHUB,
                filename=f"previous_success_{name}",
                content_hash=content_sha256(masked),
                content=masked,
                acquisition_status=AcquisitionStatus.COLLECTED,
                redaction_status=redaction,
                metadata={"previous_run_id": previous.run_id},
            )
        )
        result.available.append(ArtifactKind.PREVIOUS_SUCCESS_LOG.value)


def _first_text_from_log_archive(archive: bytes) -> tuple[str, str] | None:
    """Best-effort first text member from a GitHub Actions log ZIP (no path traversal)."""
    import io
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            for info in zf.infolist():
                if info.is_dir() or ".." in info.filename or info.filename.startswith("/"):
                    continue
                lower = info.filename.lower()
                if not (lower.endswith(".log") or lower.endswith(".txt")):
                    continue
                if info.file_size > 5_000_000:
                    continue
                raw = zf.read(info)
                return info.filename.split("/")[-1], raw.decode("utf-8", errors="replace")
    except zipfile.BadZipFile:
        return None
    return None
