export type ExecutionMode = "rules_only" | "rules_rag" | "llm_only" | "rag_llm" | "confidence_routed";
export type RetrievalMode = "embedding_only" | "hybrid_static" | "hybrid_with_history" | "keyword_only";

export interface AnalysisOptions {
  enable_rag?: boolean;
  enable_llm?: boolean;
  generate_recommendations?: boolean;
  top_k_predictions?: number;
  execution_mode?: ExecutionMode;
  retrieval_mode?: RetrievalMode | null;
  budget_usd?: number | null;
  latency_limit_ms?: number;
  risk_level?: "low" | "medium" | "high" | "critical";
}

export interface StartAnalysisRequest {
  analysis_type?: string;
  file_ids: string[];
  options?: AnalysisOptions;
}

export interface ReanalyseRequest {
  reason: string;
  file_ids?: string[];
}

export interface AnalysisAccepted {
  analysis_run_id: string;
  incident_id: string;
  status: string;
  progress_percentage: number;
  created_at: string;
}

export interface AnalysisStage {
  name: string;
  status: string;
  duration_ms: number | null;
}

export interface AnalysisStatus {
  id: string;
  incident_id: string;
  status: string;
  current_stage: string | null;
  progress_percentage: number;
  started_at: string | null;
  estimated_remaining_seconds: number | null;
  stages: AnalysisStage[];
}

export interface AnalysisRunListItem {
  id: string;
  incident_id: string;
  status: string;
  analysis_type: string;
  progress_percentage: number;
  created_at: string | null;
  completed_at: string | null;
}

export interface AnalysisOrchestrationSummary {
  requested_execution_mode: string | null;
  effective_execution_mode: string | null;
  selected_route: string | null;
  confidence: number | null;
  confidence_band: string | null;
  uncertainty_score: number | null;
  uncertainty_level: string | null;
  evidence_quality_score: number | null;
  retrieval_used: boolean;
  reasoning_used: boolean;
  fallback_used: boolean;
  fallback_reason: string | null;
  routing_policy_version: string | null;
  provider_usage_summary: Array<Record<string, unknown>>;
  cost_summary: Record<string, unknown> | null;
  latency_summary: Record<string, unknown> | null;
  retrieval_mode: string | null;
  candidates_considered: number | null;
  results_selected: number | null;
  duplicate_count: number | null;
  historical_results_used: number | null;
  retrieval_quality_score: number | null;
  retrieval_configuration_hash: string | null;
  retrieval_fallback_used: boolean;
  retrieval_fallback_reason: string | null;
}

export interface AnalysisRunDetail {
  id: string;
  incident_id: string;
  status: string;
  analysis_type: string;
  duration_ms: number | null;
  progress_percentage: number;
  current_stage: string | null;
  input_summary: Record<string, unknown> | null;
  output_summary: Record<string, unknown> | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string | null;
  completed_at: string | null;
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
  model_versions: Record<string, unknown> | null;
  orchestration: AnalysisOrchestrationSummary | null;
  limitations: string[];
  token_usage: unknown;
  cost: unknown;
  processing_time_ms: number | null;
}

export interface EvidenceItem {
  id: string;
  evidence_type: string;
  source_file: { id?: string | null; name?: string } | null;
  line_start: number | null;
  line_end: number | null;
  importance_score: number | null;
  excerpt: string | null;
  explanation: string | null;
}

export interface EvidenceListResponse {
  items: EvidenceItem[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface RetrievedSource {
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
}

export interface RetrievedSourceListResponse {
  items: RetrievedSource[];
}

export interface RecommendationItem {
  id: string;
  step_number: number;
  title: string;
  action: string;
  explanation: string | null;
  expected_result: string | null;
  risk_level: string | null;
  difficulty: string | null;
  prevention_type: string | null;
  accepted: boolean | null;
  completed: boolean;
}

export interface RecommendationListResponse {
  items: RecommendationItem[];
  summary: string | null;
  confidence_score: number | null;
  llm_model: string | null;
}
