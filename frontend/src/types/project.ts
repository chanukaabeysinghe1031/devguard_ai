export type CiProvider = "github_actions" | "gitlab" | "jenkins" | "other";
export type ProjectStatus = "active" | "paused" | "archived";

export interface ProjectCreateRequest {
  name: string;
  key: string;
  description?: string | null;
  repository_url?: string | null;
  default_branch?: string | null;
  ci_provider: CiProvider;
  cloud_provider?: string | null;
  default_environment?: string | null;
}

export interface ProjectUpdateRequest {
  description?: string | null;
  repository_url?: string | null;
  default_branch?: string | null;
  cloud_provider?: string | null;
  default_environment?: string | null;
}

export interface ProjectListItem {
  id: string;
  name: string;
  key: string;
  ci_provider: CiProvider;
  cloud_provider: string | null;
  status: ProjectStatus;
  open_incident_count: number;
  last_pipeline_run_at: string | null;
}

export interface ProjectStatistics {
  total_pipeline_runs: number;
  failed_pipeline_runs: number;
  open_incidents: number;
  resolved_incidents: number;
}

export interface Project {
  id: string;
  name: string;
  key: string;
  description: string | null;
  repository_url: string | null;
  default_branch: string | null;
  ci_provider: CiProvider;
  cloud_provider: string | null;
  default_environment: string | null;
  status: ProjectStatus;
  created_at: string | null;
  updated_at: string | null;
}

export interface ProjectDetail extends Project {
  statistics: ProjectStatistics;
}
