import { apiFetch } from "./client";
import { buildQueryString } from "./queryString";
import type {
  MessageResponse,
  PaginatedResponse,
  Project,
  ProjectCreateRequest,
  ProjectDetail,
  ProjectListItem,
  ProjectUpdateRequest,
} from "../types";

export interface ListProjectsParams {
  page?: number;
  page_size?: number;
  status?: string;
  ci_provider?: string;
  cloud_provider?: string;
  search?: string;
  sort_by?: string;
  sort_order?: string;
}

export async function listProjects(
  params: ListProjectsParams = {},
): Promise<PaginatedResponse<ProjectListItem>> {
  return apiFetch<PaginatedResponse<ProjectListItem>>(`/projects${buildQueryString(params)}`);
}

export async function getProject(projectId: string): Promise<ProjectDetail> {
  return apiFetch<ProjectDetail>(`/projects/${projectId}`);
}

export async function createProject(payload: ProjectCreateRequest): Promise<Project> {
  return apiFetch<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateProject(
  projectId: string,
  payload: ProjectUpdateRequest,
): Promise<Project> {
  return apiFetch<Project>(`/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function archiveProject(projectId: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>(`/projects/${projectId}/archive`, { method: "POST" });
}

export async function restoreProject(projectId: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>(`/projects/${projectId}/restore`, { method: "POST" });
}
