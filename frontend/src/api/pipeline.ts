import { apiFetch } from "./client";

export type AnalysisDetail = {
  id: string;
  incident_id: string;
  status: string;
  progress_percentage: number;
  current_stage: string | null;
  duration_ms: number | null;
  processing_time_ms: number | null;
  classification: {
    category?: string;
    confidence?: number;
    rank?: number;
  } | null;
  root_cause: {
    summary?: string;
    confidence?: number;
  } | null;
  evidence_count: number;
  recommendation_count: number;
  retrieved_document_count: number;
  limitations: string[];
  token_usage: unknown;
  cost: unknown;
  orchestration: {
    selected_route?: string | null;
    fallback_used?: boolean;
    fallback_reason?: string | null;
    retrieval_used?: boolean;
    reasoning_used?: boolean;
    cost_summary?: unknown;
    latency_summary?: unknown;
  } | null;
  error_message: string | null;
  output_summary: Record<string, unknown> | null;
};

export type EvidenceItem = {
  id: string;
  evidence_type: string;
  excerpt: string | null;
  explanation: string | null;
  importance_score: number | null;
  line_start: number | null;
  line_end: number | null;
  source_file: { id?: string | null; name?: string } | null;
};

export type SourceItem = {
  id: string;
  rank: number;
  similarity_score: number | null;
  used_in_reasoning: boolean;
  document: {
    title: string;
    provider: string;
    source_url?: string | null;
    technology?: string;
    source_type?: string;
  };
  chunk: {
    heading?: string | null;
    content_preview: string;
    section?: string | null;
  };
};

export type RecommendationItem = {
  id: string;
  step_number: number;
  title: string;
  action: string;
  explanation: string | null;
  expected_result: string | null;
  risk_level: string | null;
};

async function ensureProject(): Promise<string> {
  const listed = await apiFetch<{ items: Array<{ id: string }> }>("/projects?page=1&page_size=1");
  if (listed.items?.[0]?.id) return listed.items[0].id;
  const created = await apiFetch<{ id: string }>("/projects", {
    method: "POST",
    body: JSON.stringify({
      name: "Diagnosis Demo",
      key: `DG${Math.random().toString(36).slice(2, 6).toUpperCase()}`,
      ci_provider: "github_actions",
    }),
  });
  return created.id;
}

export async function runDiagnosisPipeline(file: File, title: string) {
  const projectId = await ensureProject();
  const incident = await apiFetch<{ id: string }>("/incidents", {
    method: "POST",
    body: JSON.stringify({
      project_id: projectId,
      title: title || file.name,
      source: "manual_upload",
      severity: "high",
    }),
  });
  const form = new FormData();
  form.append("files", file);
  const upload = await apiFetch<{ files: Array<{ id: string }> }>(
    `/incidents/${incident.id}/files`,
    { method: "POST", formData: form },
  );
  const fileId = upload.files[0]?.id;
  if (!fileId) throw new Error("Upload did not return a file id.");

  const started = await apiFetch<{
    analysis_run_id: string;
    status: string;
    progress_percentage: number;
  }>(`/incidents/${incident.id}/analyses`, {
    method: "POST",
    body: JSON.stringify({
      analysis_type: "full",
      file_ids: [fileId],
      options: {
        enable_rag: true,
        enable_llm: true,
        generate_recommendations: true,
        // Explicit grounded path for the product diagnosis UI (Phase 3).
        // confidence_routed remains available for cost-aware orchestration experiments.
        execution_mode: "rag_llm",
        // Baseline embedding retrieval is more reliable for product KB citations
        // than hybrid rerank thresholds on a small curated knowledge_base.
        retrieval_mode: "embedding_only",
      },
    }),
  });

  return {
    incidentId: incident.id,
    fileId,
    analysisRunId: started.analysis_run_id,
    status: started.status,
    progress: started.progress_percentage,
  };
}

export async function getAnalysis(analysisRunId: string) {
  return apiFetch<AnalysisDetail>(`/analyses/${analysisRunId}`);
}

export async function getAnalysisStatus(analysisRunId: string) {
  return apiFetch<{
    id: string;
    status: string;
    progress_percentage: number;
    current_stage: string | null;
  }>(`/analyses/${analysisRunId}/status`);
}

export async function getEvidence(analysisRunId: string) {
  return apiFetch<{ items: EvidenceItem[] }>(`/analyses/${analysisRunId}/evidence`);
}

export async function getSources(analysisRunId: string) {
  return apiFetch<{ items: SourceItem[] }>(`/analyses/${analysisRunId}/sources`);
}

export async function getRecommendations(analysisRunId: string) {
  return apiFetch<{ items: RecommendationItem[]; summary?: string | null }>(
    `/analyses/${analysisRunId}/recommendations`,
  );
}

export type HistoryItem = {
  id: string;
  title: string;
  status: string;
  incidentId: string;
};

/** Load recent analyses from persisted incidents (survives refresh/logout+login). */
export async function listRecentAnalysisHistory(limit = 8): Promise<HistoryItem[]> {
  const incidents = await apiFetch<{
    items: Array<{ id: string; title: string }>;
  }>("/incidents?page=1&page_size=20");
  const items: HistoryItem[] = [];
  for (const incident of incidents.items || []) {
    const analyses = await apiFetch<
      Array<{ id: string; status: string; created_at?: string }>
    >(`/incidents/${incident.id}/analyses`);
    for (const analysis of analyses || []) {
      items.push({
        id: analysis.id,
        title: incident.title,
        status: analysis.status,
        incidentId: incident.id,
      });
    }
  }
  return items.slice(0, limit);
}
