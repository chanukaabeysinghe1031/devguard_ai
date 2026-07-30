"""GitHub App provider boundary (ADR-005).

The application layer depends on this Protocol only; the concrete GitHub App
client and the deterministic test double live in ``app.infrastructure.integrations``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class GitHubInstallationInfo:
    installation_id: int
    account_login: str
    account_id: int | None = None
    account_type: str | None = None
    repository_selection: str | None = None
    permissions: dict[str, str] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class GitHubRepositoryInfo:
    repository_id: int
    full_name: str
    default_branch: str | None = None
    html_url: str | None = None
    private: bool = True


@dataclass(frozen=True, slots=True)
class GitHubWorkflowRunInfo:
    run_id: int
    repository_full_name: str
    name: str | None = None
    workflow_id: int | None = None
    run_number: int | None = None
    run_attempt: int | None = None
    event: str | None = None
    status: str | None = None
    conclusion: str | None = None
    head_branch: str | None = None
    head_sha: str | None = None
    html_url: str | None = None
    actor_login: str | None = None
    run_started_at: datetime | None = None
    updated_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GitHubWorkflowInfo:
    workflow_id: int
    name: str
    path: str | None = None
    state: str | None = None


@runtime_checkable
class GitHubProvider(Protocol):
    """Read-only GitHub App operations. No write permissions are ever used."""

    @property
    def name(self) -> str: ...

    async def get_installation(self, installation_id: int) -> GitHubInstallationInfo: ...

    async def list_installation_repositories(
        self,
        installation_id: int,
    ) -> list[GitHubRepositoryInfo]: ...

    async def list_repository_workflows(
        self,
        *,
        installation_id: int,
        repository_full_name: str,
    ) -> list[GitHubWorkflowInfo]: ...

    async def get_workflow_run(
        self,
        *,
        installation_id: int,
        repository_full_name: str,
        run_id: int,
    ) -> GitHubWorkflowRunInfo: ...

    async def download_workflow_run_logs(
        self,
        *,
        installation_id: int,
        repository_full_name: str,
        run_id: int,
    ) -> bytes | None: ...
