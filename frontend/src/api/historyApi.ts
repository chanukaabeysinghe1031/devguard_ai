import { apiFetch } from "./client";
import { buildQueryString } from "./queryString";
import type { PaginatedResponse } from "../types/common";
import type { HistoryIncidentItem } from "../types/history";

export interface HistorySearchParams {
  page?: number;
  page_size?: number;
  search?: string;
  project_id?: string;
  provider?: string;
  category?: string;
  severity?: string;
  status?: string;
  environment?: string;
  resolved_by?: string;
  date_from?: string;
  date_to?: string;
  sort_by?: string;
  sort_order?: string;
}

export async function searchIncidentHistory(
  params: HistorySearchParams = {},
): Promise<PaginatedResponse<HistoryIncidentItem>> {
  return apiFetch<PaginatedResponse<HistoryIncidentItem>>(`/history/incidents${buildQueryString(params)}`);
}
