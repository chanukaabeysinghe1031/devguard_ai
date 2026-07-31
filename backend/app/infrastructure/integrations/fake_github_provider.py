"""Deterministic GitHub provider double used by tests and local development.

Never selected in production — ``Settings.validate_for_runtime`` rejects
``GITHUB_PROVIDER=fake`` outside development/staging.
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime

from app.domain.interfaces.github_provider import (
    GitHubChangedFileInfo,
    GitHubCommitInfo,
    GitHubCompareInfo,
    GitHubInstallationInfo,
    GitHubRepositoryInfo,
    GitHubWorkflowInfo,
    GitHubWorkflowRunInfo,
)

FAKE_INSTALLATION_ID = 12345678
FAKE_ACCOUNT_LOGIN = "devguard-fixtures"
FAKE_REPOSITORY_ID = 987654321
FAKE_REPOSITORY_FULL_NAME = "devguard-fixtures/demo-service"
FAKE_DEFAULT_BRANCH = "main"

FAKE_LOG_CONTENT = """2026-07-30T10:15:02.1234567Z ##[group]Run docker build -t demo-service:ci .
2026-07-30T10:15:11.9876543Z Step 6/9 : COPY build/libs/demo-service.jar app.jar
2026-07-30T10:15:12.0004311Z COPY failed: file not found in build context or excluded by \
.dockerignore: stat build/libs/demo-service.jar: file does not exist
2026-07-30T10:15:12.0102233Z ##[error]Process completed with exit code 1.
"""

FAKE_SUCCESS_LOG_CONTENT = (
    "2026-07-29T10:15:02.1234567Z ##[group]Run docker build -t demo-service:ci .\n"
    "2026-07-29T10:15:11.9876543Z Successfully built demo-service:ci\n"
    "2026-07-29T10:15:12.0102233Z ##[endgroup]\n"
)

FAKE_WORKFLOW_YAML = """name: CI
on:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: docker build -t demo-service:ci .
"""

FAKE_HEAD_SHA = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
FAKE_PREV_SHA = "b2c3d4e5f60718293a4b5c6d7e8f901234567890"
FAKE_SUCCESS_RUN_ID = 40


def build_fake_log_archive() -> bytes:
    """Return a ZIP archive shaped like an Actions run log download."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("1_build.log", FAKE_LOG_CONTENT)
        archive.writestr("build/2_Set up job.txt", "2026-07-30T10:14:59.0000000Z Job started\n")
    return buffer.getvalue()


class FakeGitHubProvider:
    """In-memory provider returning stable fixtures."""

    def __init__(self, *, log_archive: bytes | None = None) -> None:
        self._log_archive = log_archive if log_archive is not None else build_fake_log_archive()
        self.downloaded_runs: list[int] = []
        self.file_reads: list[tuple[str, str]] = []

    @property
    def name(self) -> str:
        return "fake_github"

    async def get_installation(self, installation_id: int) -> GitHubInstallationInfo:
        return GitHubInstallationInfo(
            installation_id=installation_id,
            account_login=FAKE_ACCOUNT_LOGIN,
            account_id=4242,
            account_type="Organization",
            repository_selection="selected",
            permissions={"actions": "read", "metadata": "read"},
            created_at=datetime(2026, 7, 30, 9, 0, tzinfo=UTC),
        )

    async def list_installation_repositories(
        self,
        installation_id: int,
    ) -> list[GitHubRepositoryInfo]:
        return [
            GitHubRepositoryInfo(
                repository_id=FAKE_REPOSITORY_ID,
                full_name=FAKE_REPOSITORY_FULL_NAME,
                default_branch=FAKE_DEFAULT_BRANCH,
                html_url=f"https://github.com/{FAKE_REPOSITORY_FULL_NAME}",
                private=True,
            ),
            GitHubRepositoryInfo(
                repository_id=FAKE_REPOSITORY_ID + 1,
                full_name="devguard-fixtures/infra",
                default_branch="main",
                html_url="https://github.com/devguard-fixtures/infra",
                private=True,
            ),
        ]

    async def list_repository_workflows(
        self,
        *,
        installation_id: int,
        repository_full_name: str,
    ) -> list[GitHubWorkflowInfo]:
        return [
            GitHubWorkflowInfo(
                workflow_id=1,
                name="CI",
                path=".github/workflows/ci.yml",
                state="active",
            ),
            GitHubWorkflowInfo(
                workflow_id=2,
                name="Deploy",
                path=".github/workflows/deploy.yml",
                state="active",
            ),
        ]

    async def get_workflow_run(
        self,
        *,
        installation_id: int,
        repository_full_name: str,
        run_id: int,
    ) -> GitHubWorkflowRunInfo:
        return GitHubWorkflowRunInfo(
            run_id=run_id,
            repository_full_name=repository_full_name,
            name="CI",
            workflow_id=1,
            run_number=41,
            run_attempt=1,
            event="push",
            status="completed",
            conclusion="failure",
            head_branch=FAKE_DEFAULT_BRANCH,
            head_sha=FAKE_HEAD_SHA,
            html_url=f"https://github.com/{repository_full_name}/actions/runs/{run_id}",
            actor_login="octocat",
            run_started_at=datetime(2026, 7, 30, 10, 14, tzinfo=UTC),
            updated_at=datetime(2026, 7, 30, 10, 16, tzinfo=UTC),
        )

    async def download_workflow_run_logs(
        self,
        *,
        installation_id: int,
        repository_full_name: str,
        run_id: int,
    ) -> bytes | None:
        self.downloaded_runs.append(run_id)
        if run_id == FAKE_SUCCESS_RUN_ID:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("1_build.log", FAKE_SUCCESS_LOG_CONTENT)
            return buffer.getvalue()
        return self._log_archive

    async def get_repository_file_content(
        self,
        *,
        installation_id: int,
        repository_full_name: str,
        path: str,
        ref: str,
    ) -> str | None:
        self.file_reads.append((path, ref))
        if path.endswith((".yml", ".yaml")):
            return FAKE_WORKFLOW_YAML
        return None

    async def get_commit(
        self,
        *,
        installation_id: int,
        repository_full_name: str,
        sha: str,
    ) -> GitHubCommitInfo | None:
        return GitHubCommitInfo(
            sha=sha,
            message="ci: rebuild jar artifact",
            author_login="octocat",
            html_url=f"https://github.com/{repository_full_name}/commit/{sha}",
            parents=[FAKE_PREV_SHA],
        )

    async def compare_commits(
        self,
        *,
        installation_id: int,
        repository_full_name: str,
        base: str,
        head: str,
    ) -> GitHubCompareInfo | None:
        return GitHubCompareInfo(
            base_sha=base,
            head_sha=head,
            status="ahead",
            ahead_by=1,
            behind_by=0,
            total_commits=1,
            files=[
                GitHubChangedFileInfo(
                    filename="Dockerfile",
                    status="modified",
                    additions=2,
                    deletions=1,
                    changes=3,
                ),
                GitHubChangedFileInfo(
                    filename="build.gradle",
                    status="modified",
                    additions=1,
                    deletions=0,
                    changes=1,
                ),
            ],
        )

    async def list_workflow_runs(
        self,
        *,
        installation_id: int,
        repository_full_name: str,
        workflow_id: int | None = None,
        branch: str | None = None,
        status: str | None = None,
        per_page: int = 10,
    ) -> list[GitHubWorkflowRunInfo]:
        success = GitHubWorkflowRunInfo(
            run_id=FAKE_SUCCESS_RUN_ID,
            repository_full_name=repository_full_name,
            name="CI",
            workflow_id=workflow_id or 1,
            run_number=40,
            run_attempt=1,
            event="push",
            status="completed",
            conclusion="success",
            head_branch=branch or FAKE_DEFAULT_BRANCH,
            head_sha=FAKE_PREV_SHA,
            html_url=f"https://github.com/{repository_full_name}/actions/runs/{FAKE_SUCCESS_RUN_ID}",
            actor_login="octocat",
            run_started_at=datetime(2026, 7, 29, 10, 14, tzinfo=UTC),
            updated_at=datetime(2026, 7, 29, 10, 16, tzinfo=UTC),
        )
        if status == "completed" or status is None:
            return [success]
        return []
