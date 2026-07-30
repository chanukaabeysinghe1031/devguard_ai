export type PipelineRunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface PipelineRunCreateRequest {
  external_run_id?: string | null;
  provider: string;
  workflow_name?: string | null;
  branch?: string | null;
  commit_sha?: string | null;
  triggered_by?: string | null;
  environment?: string | null;
  status: PipelineRunStatus;
  started_at?: string | null;
  completed_at?: string | null;
  source_url?: string | null;
  raw_metadata?: Record<string, unknown> | null;
}

export interface PipelineRun {
  id: string;
  project_id: string;
  external_run_id: string | null;
  provider: string;
  workflow_name: string | null;
  branch: string | null;
  commit_sha: string | null;
  triggered_by: string | null;
  environment: string | null;
  status: PipelineRunStatus;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  source_url: string | null;
  incident_count: number;
  created_at: string | null;
}
