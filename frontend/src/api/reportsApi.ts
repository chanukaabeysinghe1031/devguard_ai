import { apiFetch, API_BASE, loadSession } from "./client";
import { buildQueryString } from "./queryString";
import type { PaginatedResponse } from "../types/common";
import type { ReportDetail, ReportListItem } from "../types/report";

export interface ListReportsParams {
  page?: number;
  page_size?: number;
  incident_id?: string;
  project_id?: string;
}

export async function listReports(
  params: ListReportsParams = {},
): Promise<PaginatedResponse<ReportListItem>> {
  return apiFetch<PaginatedResponse<ReportListItem>>(`/reports${buildQueryString(params)}`);
}

export async function getReport(reportId: string): Promise<ReportDetail> {
  return apiFetch<ReportDetail>(`/reports/${reportId}`);
}

/** Builds an authenticated download URL. Fetch with credentials via fetchReportBlob for downloads. */
export function reportDownloadUrl(reportId: string): string {
  return `${API_BASE}/reports/${reportId}/download`;
}

export async function fetchReportBlob(reportId: string): Promise<Blob> {
  const session = loadSession();
  const headers = new Headers();
  if (session?.accessToken) headers.set("Authorization", `Bearer ${session.accessToken}`);
  if (session?.organizationId) headers.set("X-Organization-Id", session.organizationId);
  const response = await fetch(reportDownloadUrl(reportId), { headers });
  if (!response.ok) {
    throw new Error(`Failed to download report (status ${response.status}).`);
  }
  return response.blob();
}
