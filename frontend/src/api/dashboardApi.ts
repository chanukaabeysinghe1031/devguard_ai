import { apiFetch } from "./client";
import { buildQueryString } from "./queryString";
import type {
  ActiveAnalysesResponse,
  ActivityResponse,
  DashboardSummary,
  FailureCategoryDistribution,
  IncidentTrend,
  RecentIncidentsResponse,
  SeverityDistribution,
} from "../types/dashboard";

export interface DashboardParams {
  project_id?: string;
  date_from?: string;
  date_to?: string;
}

export async function getDashboardSummary(params: DashboardParams = {}): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>(`/dashboard/summary${buildQueryString(params)}`);
}

export async function getIncidentTrend(
  params: DashboardParams & { interval?: string } = {},
): Promise<IncidentTrend> {
  return apiFetch<IncidentTrend>(`/dashboard/incident-trend${buildQueryString(params)}`);
}

export async function getSeverityDistribution(
  params: DashboardParams = {},
): Promise<SeverityDistribution> {
  return apiFetch<SeverityDistribution>(`/dashboard/severity-distribution${buildQueryString(params)}`);
}

export async function getFailureCategories(
  params: DashboardParams = {},
): Promise<FailureCategoryDistribution> {
  return apiFetch<FailureCategoryDistribution>(`/dashboard/failure-categories${buildQueryString(params)}`);
}

export async function getRecentIncidents(
  params: DashboardParams & { limit?: number } = {},
): Promise<RecentIncidentsResponse> {
  return apiFetch<RecentIncidentsResponse>(`/dashboard/recent-incidents${buildQueryString(params)}`);
}

export async function getActiveAnalyses(
  params: DashboardParams & { limit?: number } = {},
): Promise<ActiveAnalysesResponse> {
  return apiFetch<ActiveAnalysesResponse>(`/dashboard/active-analyses${buildQueryString(params)}`);
}

export async function getDashboardActivity(
  params: DashboardParams & { limit?: number } = {},
): Promise<ActivityResponse> {
  return apiFetch<ActivityResponse>(`/dashboard/activity${buildQueryString(params)}`);
}
