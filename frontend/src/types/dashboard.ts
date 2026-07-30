import type { IncidentListItem } from "./incident";

export interface DashboardSummary {
  open_incidents: number;
  critical_incidents: number;
  active_analyses: number;
  resolved_today: number;
  failed_deployments: number;
  successful_deployments: number;
  average_resolution_minutes: number | null;
  deployment_success_rate: number | null;
}

export interface IncidentTrendItem {
  period: string;
  incident_count: number;
  resolved_count: number;
}

export interface IncidentTrend {
  interval: string;
  items: IncidentTrendItem[];
}

export interface SeverityDistribution {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface FailureCategoryItem {
  category: string;
  count: number;
}

export interface FailureCategoryDistribution {
  items: FailureCategoryItem[];
}

export interface ActiveAnalysisItem {
  id: string;
  incident_id: string;
  incident_number: string;
  incident_title: string;
  status: string;
  current_stage: string | null;
  progress_percentage: number;
  started_at: string | null;
}

export interface ActivityItem {
  id: string;
  incident_id: string;
  incident_number: string;
  event_type: string;
  title: string;
  description: string | null;
  occurred_at: string;
  actor_user_id: string | null;
}

export interface RecentIncidentsResponse {
  items: IncidentListItem[];
}

export interface ActiveAnalysesResponse {
  items: ActiveAnalysisItem[];
}

export interface ActivityResponse {
  items: ActivityItem[];
}
