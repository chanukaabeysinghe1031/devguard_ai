export type IncidentStatus =
  | "detected"
  | "analysing"
  | "open"
  | "in_progress"
  | "resolved"
  | "closed"
  | "analysis_failed"
  | "ignored"
  | "false_positive"
  | "reopened";

export type IncidentSeverity = "critical" | "high" | "medium" | "low";
export type IncidentPriority = "urgent" | "high" | "normal" | "low";

export interface IncidentCreateRequest {
  project_id: string;
  pipeline_run_id?: string | null;
  title: string;
  description?: string | null;
  source: string;
  severity: IncidentSeverity;
  priority?: IncidentPriority | null;
  environment?: string | null;
}

export interface IncidentUpdateRequest {
  title?: string;
  severity?: IncidentSeverity;
  priority?: IncidentPriority;
  tags?: string[];
}

export interface IncidentStatusChangeRequest {
  status: IncidentStatus;
  comment?: string | null;
}

export interface ProjectSummary {
  id: string;
  name: string;
  key: string | null;
}

export interface PipelineRunSummary {
  id: string;
  external_run_id: string | null;
  provider: string | null;
  workflow_name: string | null;
  source_url: string | null;
}

export interface AssigneeSummary {
  id: string;
  email: string;
  full_name: string;
}

export interface LatestAnalysisSummary {
  id: string;
  status: string;
  classification: Record<string, unknown> | null;
  root_cause_summary: string | null;
}

export interface IncidentListItem {
  id: string;
  incident_number: string;
  title: string;
  project: ProjectSummary;
  severity: IncidentSeverity;
  status: IncidentStatus;
  environment: string | null;
  predicted_category: string | null;
  ai_confidence: number | null;
  detected_at: string;
  current_assignee: AssigneeSummary | null;
  /** Optional: present when the backend includes it on the list response. */
  source?: string | null;
}

export interface Incident {
  id: string;
  incident_number: string;
  project_id: string;
  pipeline_run_id: string | null;
  title: string;
  description: string | null;
  source: string;
  status: IncidentStatus;
  severity: IncidentSeverity;
  priority: IncidentPriority | null;
  environment: string | null;
  detected_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  created_at: string | null;
  tags: string[] | null;
}

export interface IncidentDetail extends Incident {
  project: ProjectSummary;
  pipeline_run: PipelineRunSummary | null;
  latest_analysis: LatestAnalysisSummary | null;
  current_assignee: AssigneeSummary | null;
}

export interface TimelineEvent {
  id: string;
  event_type: string;
  actor_type: string;
  title: string;
  description: string | null;
  occurred_at: string;
}

export interface IncidentNote {
  id: string;
  incident_id: string;
  author_id: string;
  note_type: string;
  content: string;
  is_pinned: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface NoteCreateRequest {
  note_type: string;
  content: string;
  is_pinned?: boolean;
}

export interface ResolutionSummary {
  id: string;
  resolution_summary: string;
  confirmed_root_cause: string;
  resolution_steps: string[] | null;
  prevention_actions: string[] | null;
  time_spent_minutes: number | null;
  ai_recommendation_used: boolean | null;
  created_at: string | null;
}

export interface ResolveIncidentRequest {
  resolution_summary: string;
  confirmed_root_cause: string;
  resolution_steps: string[];
  prevention_actions: string[];
  time_spent_minutes?: number | null;
  ai_recommendation_used?: boolean | null;
}

export interface ReopenIncidentRequest {
  reason: string;
}

export interface AcknowledgeResponse {
  success: boolean;
  acknowledged_at: string;
}

export interface IncidentAssignRequest {
  user_id: string;
  reason?: string | null;
}
