/** Types mirroring backend/app/schemas/integration.py exactly (Phase 5B GitHub Actions ingestion). */

export type WorkflowFilterMode = "all" | "selected";
export type BranchFilterMode = "all" | "default" | "patterns";
export type GitHubConnectionStatus = "connected" | "paused" | "not_connected" | "coming_later";

export interface WorkflowFilters {
  mode: WorkflowFilterMode;
  names: string[];
}

export interface BranchFilters {
  mode: BranchFilterMode;
  patterns: string[];
}

export interface GitHubStatusResponse {
  enabled: boolean;
  provider: string;
  app_configured: boolean;
  webhook_configured: boolean;
  app_slug: string | null;
  installation_count: number;
  connection_count: number;
}

export interface InstallUrlRequest {
  project_id: string;
}

export interface InstallUrlResponse {
  install_url: string;
  state: string;
  expires_at: string;
  project_id: string;
}

export interface SetupCompleteRequest {
  installation_id: number;
  state: string;
}

export interface GitHubInstallationResponse {
  id: string;
  github_installation_id: number;
  github_account_login: string;
  account_type: string | null;
  status: string;
  repository_selection: string | null;
  permissions: Record<string, string> | null;
  installed_at: string | null;
  created_at: string;
  /** This organization's own access grant status (a shared installation may
   * be active while this organization's grant is disconnected, or vice versa). */
  organization_access_status: string | null;
}

export interface GitHubInstallationListResponse {
  items: GitHubInstallationResponse[];
}

export interface SetupCompleteResponse {
  installation: GitHubInstallationResponse;
  project_id: string | null;
  redirect_url: string | null;
}

export interface GitHubRepositoryResponse {
  github_repository_id: number;
  full_name: string;
  default_branch: string | null;
  html_url: string | null;
  private: boolean;
  connected_project_id: string | null;
}

export interface GitHubRepositoryListResponse {
  items: GitHubRepositoryResponse[];
}

export interface GitHubWorkflowResponse {
  workflow_id: number;
  name: string;
  path: string | null;
  state: string | null;
}

export interface GitHubWorkflowListResponse {
  items: GitHubWorkflowResponse[];
}

export interface ConnectionAutomationSettings {
  auto_create_incidents?: boolean;
  auto_start_analysis?: boolean;
  notify_on_failure?: boolean;
  workflow_filters?: WorkflowFilters | null;
  branch_filters?: BranchFilters | null;
  failure_conclusions?: string[] | null;
  environment_mapping?: Record<string, string> | null;
  severity_rules?: Record<string, string> | null;
}

export interface ConnectionCreateRequest extends ConnectionAutomationSettings {
  installation_id: string;
  github_repository_id: number;
  repository_full_name: string;
  repository_url?: string | null;
  default_branch?: string | null;
}

export interface ConnectionUpdateRequest {
  auto_create_incidents?: boolean | null;
  auto_start_analysis?: boolean | null;
  notify_on_failure?: boolean | null;
  workflow_filters?: WorkflowFilters | null;
  branch_filters?: BranchFilters | null;
  failure_conclusions?: string[] | null;
  environment_mapping?: Record<string, string> | null;
  severity_rules?: Record<string, string> | null;
}

export interface ConnectionResponse {
  id: string;
  project_id: string;
  installation_id: string;
  github_installation_id: number;
  github_repository_id: number;
  repository_full_name: string;
  repository_url: string | null;
  default_branch: string | null;
  is_active: boolean;
  is_paused: boolean;
  auto_create_incidents: boolean;
  auto_start_analysis: boolean;
  notify_on_failure: boolean;
  workflow_filters: WorkflowFilters;
  branch_filters: BranchFilters;
  failure_conclusions: string[];
  environment_mapping: Record<string, string>;
  severity_rules: Record<string, string>;
  last_webhook_at: string | null;
  last_successful_sync_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectIntegrationSummary {
  provider: string;
  display_name: string;
  status: GitHubConnectionStatus | string;
  available: boolean;
  connection: ConnectionResponse | null;
}

export interface ProjectIntegrationListResponse {
  items: ProjectIntegrationSummary[];
}

export interface ConnectionTestResponse {
  ok: boolean;
  checked_at: string;
  repository_full_name: string;
  installation_reachable: boolean;
  repository_accessible: boolean;
  message: string;
}

export interface WebhookActivityItem {
  id: string;
  delivery_id: string;
  event_name: string;
  event_action: string | null;
  processing_status: string;
  received_at: string;
  processed_at: string | null;
  error_code: string | null;
  error_message: string | null;
  workflow_name: string | null;
  branch: string | null;
  conclusion: string | null;
  related_incident_id: string | null;
  related_pipeline_run_id: string | null;
}

export interface WebhookActivityListResponse {
  items: WebhookActivityItem[];
}
