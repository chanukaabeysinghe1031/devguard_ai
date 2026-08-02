"""Integration API schemas (Phase 5B — GitHub Actions ingestion).

No secret material (App private key, webhook secret, installation tokens) is
ever represented in these models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowFilters(BaseModel):
    mode: Literal["all", "selected"] = "all"
    names: list[str] = Field(default_factory=list)


class BranchFilters(BaseModel):
    mode: Literal["all", "default", "patterns"] = "all"
    patterns: list[str] = Field(default_factory=list)


class GitHubStatusResponse(BaseModel):
    enabled: bool
    provider: str
    app_configured: bool
    webhook_configured: bool
    app_slug: str | None = None
    installation_count: int
    connection_count: int


class InstallUrlRequest(BaseModel):
    project_id: UUID


class InstallUrlResponse(BaseModel):
    install_url: str
    state: str
    expires_at: datetime
    project_id: UUID


class SetupCompleteRequest(BaseModel):
    installation_id: int = Field(gt=0)
    state: str = Field(min_length=1, max_length=4096)


class GitHubInstallationResponse(BaseModel):
    id: UUID
    github_installation_id: int
    github_account_login: str
    account_type: str | None = None
    status: str
    repository_selection: str | None = None
    permissions: dict[str, str] | None = None
    installed_at: datetime | None = None
    created_at: datetime
    # This organization's independent access grant status — a shared GitHub
    # App installation (``status`` above) may be ACTIVE while a particular
    # organization's own grant is disconnected/suspended, or vice versa.
    organization_access_status: str | None = None


class GitHubInstallationListResponse(BaseModel):
    items: list[GitHubInstallationResponse]


class SetupCompleteResponse(BaseModel):
    installation: GitHubInstallationResponse
    project_id: UUID | None = None
    redirect_url: str | None = None


class GitHubRepositoryResponse(BaseModel):
    github_repository_id: int
    full_name: str
    default_branch: str | None = None
    html_url: str | None = None
    private: bool = True
    connected_project_id: UUID | None = None


class GitHubRepositoryListResponse(BaseModel):
    items: list[GitHubRepositoryResponse]


class GitHubWorkflowResponse(BaseModel):
    workflow_id: int
    name: str
    path: str | None = None
    state: str | None = None


class GitHubWorkflowListResponse(BaseModel):
    items: list[GitHubWorkflowResponse]


class ConnectionAutomationSettings(BaseModel):
    auto_create_incidents: bool = True
    auto_start_analysis: bool = True
    notify_on_failure: bool = True
    workflow_filters: WorkflowFilters | None = None
    branch_filters: BranchFilters | None = None
    failure_conclusions: list[str] | None = None
    environment_mapping: dict[str, str] | None = None
    severity_rules: dict[str, str] | None = None


class ConnectionCreateRequest(ConnectionAutomationSettings):
    installation_id: UUID
    github_repository_id: int = Field(gt=0)
    repository_full_name: str = Field(min_length=1, max_length=500)
    repository_url: str | None = None
    default_branch: str | None = Field(default=None, max_length=255)


class ConnectionUpdateRequest(BaseModel):
    auto_create_incidents: bool | None = None
    auto_start_analysis: bool | None = None
    notify_on_failure: bool | None = None
    workflow_filters: WorkflowFilters | None = None
    branch_filters: BranchFilters | None = None
    failure_conclusions: list[str] | None = None
    environment_mapping: dict[str, str] | None = None
    severity_rules: dict[str, str] | None = None


class ConnectionResponse(BaseModel):
    id: UUID
    project_id: UUID
    installation_id: UUID
    github_installation_id: int
    github_repository_id: int
    repository_full_name: str
    repository_url: str | None = None
    default_branch: str | None = None
    is_active: bool
    is_paused: bool
    auto_create_incidents: bool
    auto_start_analysis: bool
    notify_on_failure: bool
    workflow_filters: WorkflowFilters
    branch_filters: BranchFilters
    failure_conclusions: list[str]
    environment_mapping: dict[str, str]
    severity_rules: dict[str, str]
    last_webhook_at: datetime | None = None
    last_successful_sync_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class ProjectIntegrationSummary(BaseModel):
    provider: str
    display_name: str
    status: str
    available: bool
    connection: ConnectionResponse | None = None


class ProjectIntegrationListResponse(BaseModel):
    items: list[ProjectIntegrationSummary]


class ConnectionTestResponse(BaseModel):
    ok: bool
    checked_at: datetime
    repository_full_name: str
    installation_reachable: bool
    repository_accessible: bool
    message: str


class WebhookAcceptedResponse(BaseModel):
    ok: bool = True
    delivery_id: str | None = None
    duplicate: bool = False
    processing_status: str | None = None


class WebhookActivityItem(BaseModel):
    id: UUID
    delivery_id: str
    event_name: str
    event_action: str | None = None
    processing_status: str
    received_at: datetime
    processed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    workflow_name: str | None = None
    branch: str | None = None
    conclusion: str | None = None
    related_incident_id: UUID | None = None
    related_pipeline_run_id: UUID | None = None


class WebhookActivityListResponse(BaseModel):
    items: list[WebhookActivityItem]
