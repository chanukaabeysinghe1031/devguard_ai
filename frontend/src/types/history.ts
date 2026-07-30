import type { AssigneeSummary, IncidentSeverity, IncidentStatus, ProjectSummary } from "./incident";

export interface HistoryIncidentItem {
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
  resolved_at: string | null;
  resolution_summary: string | null;
  root_cause_summary: string | null;
  current_assignee: AssigneeSummary | null;
}
