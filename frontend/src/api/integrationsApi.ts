import { apiFetch } from "./client";
import { buildQueryString } from "./queryString";
import type {
  ConnectionCreateRequest,
  ConnectionResponse,
  ConnectionTestResponse,
  ConnectionUpdateRequest,
  GitHubInstallationListResponse,
  GitHubRepositoryListResponse,
  GitHubStatusResponse,
  GitHubWorkflowListResponse,
  InstallUrlRequest,
  InstallUrlResponse,
  MessageResponse,
  ProjectIntegrationListResponse,
  SetupCompleteRequest,
  SetupCompleteResponse,
  WebhookActivityListResponse,
} from "../types";

export async function getGithubStatus(): Promise<GitHubStatusResponse> {
  return apiFetch<GitHubStatusResponse>("/integrations/github/status");
}

export async function createGithubInstallUrl(payload: InstallUrlRequest): Promise<InstallUrlResponse> {
  return apiFetch<InstallUrlResponse>("/integrations/github/install-url", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function completeGithubSetup(payload: SetupCompleteRequest): Promise<SetupCompleteResponse> {
  return apiFetch<SetupCompleteResponse>("/integrations/github/setup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listGithubInstallations(): Promise<GitHubInstallationListResponse> {
  return apiFetch<GitHubInstallationListResponse>("/integrations/github/installations");
}

export async function listInstallationRepositories(
  installationId: string,
): Promise<GitHubRepositoryListResponse> {
  return apiFetch<GitHubRepositoryListResponse>(
    `/integrations/github/installations/${installationId}/repositories`,
  );
}

export async function listProjectIntegrations(projectId: string): Promise<ProjectIntegrationListResponse> {
  return apiFetch<ProjectIntegrationListResponse>(`/projects/${projectId}/integrations`);
}

export async function getProjectGithubConnection(projectId: string): Promise<ConnectionResponse> {
  return apiFetch<ConnectionResponse>(`/projects/${projectId}/integrations/github`);
}

export async function connectProjectGithub(
  projectId: string,
  payload: ConnectionCreateRequest,
): Promise<ConnectionResponse> {
  return apiFetch<ConnectionResponse>(`/projects/${projectId}/integrations/github`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateProjectGithub(
  projectId: string,
  payload: ConnectionUpdateRequest,
): Promise<ConnectionResponse> {
  return apiFetch<ConnectionResponse>(`/projects/${projectId}/integrations/github`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function testProjectGithub(projectId: string): Promise<ConnectionTestResponse> {
  return apiFetch<ConnectionTestResponse>(`/projects/${projectId}/integrations/github/test`, {
    method: "POST",
  });
}

export async function pauseProjectGithub(projectId: string): Promise<ConnectionResponse> {
  return apiFetch<ConnectionResponse>(`/projects/${projectId}/integrations/github/pause`, {
    method: "POST",
  });
}

export async function resumeProjectGithub(projectId: string): Promise<ConnectionResponse> {
  return apiFetch<ConnectionResponse>(`/projects/${projectId}/integrations/github/resume`, {
    method: "POST",
  });
}

export async function disconnectProjectGithub(projectId: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>(`/projects/${projectId}/integrations/github`, {
    method: "DELETE",
  });
}

export async function listProjectGithubWorkflows(projectId: string): Promise<GitHubWorkflowListResponse> {
  return apiFetch<GitHubWorkflowListResponse>(`/projects/${projectId}/integrations/github/workflows`);
}

export interface ListProjectGithubActivityParams {
  limit?: number;
}

export async function listProjectGithubActivity(
  projectId: string,
  params: ListProjectGithubActivityParams = {},
): Promise<WebhookActivityListResponse> {
  return apiFetch<WebhookActivityListResponse>(
    `/projects/${projectId}/integrations/github/activity${buildQueryString(params)}`,
  );
}
