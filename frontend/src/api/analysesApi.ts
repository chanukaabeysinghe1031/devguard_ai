import { apiFetch } from "./client";
import type {
  AnalysisAccepted,
  AnalysisRunDetail,
  AnalysisRunListItem,
  AnalysisStatus,
  EvidenceListResponse,
  ReanalyseRequest,
  RecommendationListResponse,
  RetrievedSourceListResponse,
  StartAnalysisRequest,
} from "../types/analysis";

export async function startAnalysis(
  incidentId: string,
  payload: StartAnalysisRequest,
): Promise<AnalysisAccepted> {
  return apiFetch<AnalysisAccepted>(`/incidents/${incidentId}/analyses`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function reanalyseIncident(
  incidentId: string,
  payload: ReanalyseRequest,
): Promise<AnalysisAccepted> {
  return apiFetch<AnalysisAccepted>(`/incidents/${incidentId}/reanalyse`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getAnalysisStatus(analysisRunId: string): Promise<AnalysisStatus> {
  return apiFetch<AnalysisStatus>(`/analyses/${analysisRunId}/status`);
}

export async function getAnalysis(analysisRunId: string): Promise<AnalysisRunDetail> {
  return apiFetch<AnalysisRunDetail>(`/analyses/${analysisRunId}`);
}

export async function getAnalysisEvidence(
  analysisRunId: string,
  page = 1,
  pageSize = 50,
): Promise<EvidenceListResponse> {
  return apiFetch<EvidenceListResponse>(
    `/analyses/${analysisRunId}/evidence?page=${page}&page_size=${pageSize}`,
  );
}

export async function getAnalysisSources(analysisRunId: string): Promise<RetrievedSourceListResponse> {
  return apiFetch<RetrievedSourceListResponse>(`/analyses/${analysisRunId}/sources`);
}

export async function getAnalysisRecommendations(
  analysisRunId: string,
): Promise<RecommendationListResponse> {
  return apiFetch<RecommendationListResponse>(`/analyses/${analysisRunId}/recommendations`);
}

export async function cancelAnalysis(analysisRunId: string): Promise<AnalysisRunDetail> {
  return apiFetch<AnalysisRunDetail>(`/analyses/${analysisRunId}/cancel`, { method: "POST" });
}

export async function listIncidentAnalyses(incidentId: string): Promise<AnalysisRunListItem[]> {
  return apiFetch<AnalysisRunListItem[]>(`/incidents/${incidentId}/analyses`);
}
