/**
 * User-facing labels for Module 8/9 execution and retrieval modes.
 * Raw route/mode identifiers belong only in the admin diagnostics drawer.
 */

import type { AnalysisOrchestrationSummary } from "../types/analysis";

const EXECUTION_MODE_LABELS: Record<string, string> = {
  rules_only: "Rule-based diagnosis",
  rules_rag: "Rule-based grounded diagnosis",
  llm_only: "External reasoning without retrieved context",
  rag_llm: "Grounded AI diagnosis",
  confidence_routed: "Adaptive grounded diagnosis",
};

const RETRIEVAL_MODE_LABELS: Record<string, string> = {
  embedding_only: "Semantic search",
  hybrid_static: "Hybrid search",
  hybrid_with_history: "Hybrid search + historical incidents",
  keyword_only: "Keyword search",
};

const CONFIDENCE_BAND_LABELS: Record<string, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
  insufficient: "Insufficient evidence",
};

const ROUTE_LABELS: Record<string, string> = {
  deterministic_only: "Local rules only",
  rag_then_local: "Local grounded fallback",
  rag_then_external: "Grounded AI diagnosis",
  external_llm_without_rag: "External reasoning without retrieved context",
  insufficient_evidence: "Insufficient evidence",
};

export function executionModeLabel(mode: string | null | undefined): string {
  if (!mode) return "Standard analysis";
  return EXECUTION_MODE_LABELS[mode] ?? "Standard analysis";
}

export function retrievalModeLabel(mode: string | null | undefined): string {
  if (!mode) return "—";
  return RETRIEVAL_MODE_LABELS[mode] ?? "Knowledge retrieval";
}

export function confidenceBandLabel(band: string | null | undefined): string {
  if (!band) return "—";
  return CONFIDENCE_BAND_LABELS[band] ?? band;
}

/**
 * Prefer the actual effective route/fallback over the requested mode button label.
 */
export function effectiveDiagnosisLabel(
  orchestration: AnalysisOrchestrationSummary | null | undefined,
): string {
  if (!orchestration) return "Standard analysis";

  if (orchestration.fallback_used) {
    if (orchestration.retrieval_used && !orchestration.reasoning_used) {
      return "Local grounded fallback";
    }
    if (!orchestration.retrieval_used && orchestration.reasoning_used) {
      return "External reasoning without retrieved context";
    }
    if (orchestration.fallback_reason?.toLowerCase().includes("insufficient")) {
      return "Insufficient evidence";
    }
  }

  const route = orchestration.selected_route;
  if (route && ROUTE_LABELS[route]) {
    return ROUTE_LABELS[route];
  }

  if (orchestration.retrieval_used && orchestration.reasoning_used) {
    return "Grounded AI diagnosis";
  }
  if (orchestration.retrieval_used && !orchestration.reasoning_used) {
    return "Local grounded fallback";
  }
  if (!orchestration.retrieval_used && orchestration.reasoning_used) {
    return "External reasoning without retrieved context";
  }

  return executionModeLabel(orchestration.effective_execution_mode);
}

export function relevanceBand(score: number | null | undefined): {
  label: string;
  tone: "success" | "warning" | "danger" | "neutral";
} {
  if (score === null || score === undefined) {
    return { label: "Unknown relevance", tone: "neutral" };
  }
  if (score >= 0.55) return { label: "High relevance", tone: "success" };
  if (score >= 0.35) return { label: "Medium relevance", tone: "warning" };
  return { label: "Low relevance", tone: "danger" };
}

/** Drop very weak retrieval hits from the primary product view. */
export function filterRelevantSources<T extends { similarity_score: number | null; used_in_reasoning: boolean }>(
  items: T[],
  minScore = 0.28,
): T[] {
  const strong = items.filter(
    (item) => item.used_in_reasoning || (item.similarity_score !== null && item.similarity_score >= minScore),
  );
  return strong.length > 0 ? strong : items.slice(0, 3);
}

/** Avoid rendering duplicated summary/action/explanation text. */
export function uniqueRecommendationText(...parts: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of parts) {
    const text = (part ?? "").trim();
    if (!text) continue;
    const key = text.toLowerCase().replace(/\s+/g, " ");
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(text);
  }
  return out;
}
