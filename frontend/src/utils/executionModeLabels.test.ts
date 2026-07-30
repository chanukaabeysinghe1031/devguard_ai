import { describe, expect, it } from "vitest";

import {
  effectiveDiagnosisLabel,
  filterRelevantSources,
  relevanceBand,
  uniqueRecommendationText,
} from "./executionModeLabels";
import type { AnalysisOrchestrationSummary } from "../types/analysis";

function orch(partial: Partial<AnalysisOrchestrationSummary>): AnalysisOrchestrationSummary {
  return {
    requested_execution_mode: null,
    effective_execution_mode: null,
    selected_route: null,
    confidence: null,
    confidence_band: null,
    uncertainty_score: null,
    uncertainty_level: null,
    evidence_quality_score: null,
    retrieval_used: false,
    reasoning_used: false,
    fallback_used: false,
    fallback_reason: null,
    routing_policy_version: null,
    provider_usage_summary: [],
    cost_summary: null,
    latency_summary: null,
    retrieval_mode: null,
    candidates_considered: null,
    results_selected: null,
    duplicate_count: null,
    historical_results_used: null,
    retrieval_quality_score: null,
    retrieval_configuration_hash: null,
    retrieval_fallback_used: false,
    retrieval_fallback_reason: null,
    ...partial,
  };
}

describe("executionModeLabels", () => {
  it("labels external route without implying grounded retrieval", () => {
    expect(
      effectiveDiagnosisLabel(
        orch({
          selected_route: "external_llm_without_rag",
          retrieval_used: false,
          reasoning_used: true,
        }),
      ),
    ).toBe("External reasoning without retrieved context");
  });

  it("labels local grounded fallback when retrieval ran without external reasoning", () => {
    expect(
      effectiveDiagnosisLabel(
        orch({
          fallback_used: true,
          retrieval_used: true,
          reasoning_used: false,
        }),
      ),
    ).toBe("Local grounded fallback");
  });

  it("maps similarity into relevance bands", () => {
    expect(relevanceBand(0.7).label).toBe("High relevance");
    expect(relevanceBand(0.4).label).toBe("Medium relevance");
    expect(relevanceBand(0.1).label).toBe("Low relevance");
  });

  it("filters weak sources while keeping used-in-reasoning hits", () => {
    const filtered = filterRelevantSources([
      { similarity_score: 0.1, used_in_reasoning: false },
      { similarity_score: 0.6, used_in_reasoning: false },
      { similarity_score: 0.05, used_in_reasoning: true },
    ]);
    expect(filtered).toHaveLength(2);
  });

  it("deduplicates recommendation text", () => {
    expect(uniqueRecommendationText("Fix IAM role", "Fix IAM role", "Verify access")).toEqual([
      "Fix IAM role",
      "Verify access",
    ]);
  });
});
