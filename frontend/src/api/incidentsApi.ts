import { apiFetch } from "./client";
import { buildQueryString } from "./queryString";
import type {
  AcknowledgeResponse,
  Incident,
  IncidentAssignRequest,
  IncidentCreateRequest,
  IncidentDetail,
  IncidentListItem,
  IncidentNote,
  IncidentStatusChangeRequest,
  IncidentUpdateRequest,
  MessageResponse,
  NoteCreateRequest,
  PaginatedResponse,
  ReopenIncidentRequest,
  ResolutionSummary,
  ResolveIncidentRequest,
  TimelineEvent,
} from "../types";
import type { ReportGenerateRequest, ReportGenerateResponse } from "../types/report";

export interface ListIncidentsParams {
  page?: number;
  page_size?: number;
  project_id?: string;
  pipeline_run_id?: string;
  status?: string;
  severity?: string;
  priority?: string;
  environment?: string;
  assignee_id?: string;
  source?: string;
  search?: string;
  date_from?: string;
  date_to?: string;
  sort_by?: string;
  sort_order?: string;
}

export async function listIncidents(
  params: ListIncidentsParams = {},
): Promise<PaginatedResponse<IncidentListItem>> {
  return apiFetch<PaginatedResponse<IncidentListItem>>(`/incidents${buildQueryString(params)}`);
}

export async function getIncident(incidentId: string): Promise<IncidentDetail> {
  return apiFetch<IncidentDetail>(`/incidents/${incidentId}`);
}

export async function createIncident(payload: IncidentCreateRequest): Promise<Incident> {
  return apiFetch<Incident>("/incidents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateIncident(
  incidentId: string,
  payload: IncidentUpdateRequest,
): Promise<Incident> {
  return apiFetch<Incident>(`/incidents/${incidentId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function changeIncidentStatus(
  incidentId: string,
  payload: IncidentStatusChangeRequest,
): Promise<Incident> {
  return apiFetch<Incident>(`/incidents/${incidentId}/status`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function assignIncident(
  incidentId: string,
  payload: IncidentAssignRequest,
): Promise<Incident> {
  return apiFetch<Incident>(`/incidents/${incidentId}/assign`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function unassignIncident(incidentId: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>(`/incidents/${incidentId}/unassign`, { method: "POST" });
}

export async function acknowledgeIncident(incidentId: string): Promise<AcknowledgeResponse> {
  return apiFetch<AcknowledgeResponse>(`/incidents/${incidentId}/acknowledge`, { method: "POST" });
}

export async function getIncidentTimeline(incidentId: string): Promise<{ items: TimelineEvent[] }> {
  return apiFetch<{ items: TimelineEvent[] }>(`/incidents/${incidentId}/timeline`);
}

export async function listIncidentNotes(incidentId: string): Promise<IncidentNote[]> {
  return apiFetch<IncidentNote[]>(`/incidents/${incidentId}/notes`);
}

export async function addIncidentNote(
  incidentId: string,
  payload: NoteCreateRequest,
): Promise<IncidentNote> {
  return apiFetch<IncidentNote>(`/incidents/${incidentId}/notes`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateIncidentNote(
  noteId: string,
  payload: { content?: string; is_pinned?: boolean },
): Promise<IncidentNote> {
  return apiFetch<IncidentNote>(`/notes/${noteId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteIncidentNote(noteId: string): Promise<void> {
  await apiFetch<void>(`/notes/${noteId}`, { method: "DELETE" });
}

export async function resolveIncident(
  incidentId: string,
  payload: ResolveIncidentRequest,
): Promise<{ incident_id: string; status: string; resolved_at: string; resolution: ResolutionSummary }> {
  return apiFetch(`/incidents/${incidentId}/resolve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function reopenIncident(
  incidentId: string,
  payload: ReopenIncidentRequest,
): Promise<{ incident_id: string; status: string; message: string }> {
  return apiFetch(`/incidents/${incidentId}/reopen`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listIncidentResolutions(incidentId: string): Promise<ResolutionSummary[]> {
  return apiFetch<ResolutionSummary[]>(`/incidents/${incidentId}/resolutions`);
}

export async function generateIncidentReport(
  incidentId: string,
  payload: ReportGenerateRequest = {},
): Promise<ReportGenerateResponse> {
  return apiFetch<ReportGenerateResponse>(`/incidents/${incidentId}/reports`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
