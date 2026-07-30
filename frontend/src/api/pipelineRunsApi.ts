import { apiFetch } from "./client";
import { buildQueryString } from "./queryString";
import type { PaginatedResponse, PipelineRun, PipelineRunCreateRequest } from "../types";

export interface ListPipelineRunsParams {
  page?: number;
  page_size?: number;
  status?: string;
  provider?: string;
  environment?: string;
  branch?: string;
  date_from?: string;
  date_to?: string;
}

export async function listPipelineRuns(
  projectId: string,
  params: ListPipelineRunsParams = {},
): Promise<PaginatedResponse<PipelineRun>> {
  return apiFetch<PaginatedResponse<PipelineRun>>(
    `/projects/${projectId}/pipeline-runs${buildQueryString(params)}`,
  );
}

export async function createPipelineRun(
  projectId: string,
  payload: PipelineRunCreateRequest,
): Promise<PipelineRun> {
  return apiFetch<PipelineRun>(`/projects/${projectId}/pipeline-runs`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getPipelineRun(pipelineRunId: string): Promise<PipelineRun> {
  return apiFetch<PipelineRun>(`/pipeline-runs/${pipelineRunId}`);
}
