import { apiFetch } from "./client";

export type LatestEvaluationMetrics = {
  run_dir?: string;
  labels_mode?: string;
  benchmark_version?: string;
  aggregate_metrics?: Record<string, number>;
  validation?: Record<string, unknown>;
};

export function getLatestEvaluationMetrics(): Promise<LatestEvaluationMetrics> {
  return apiFetch<LatestEvaluationMetrics>("/evaluation/latest-metrics");
}
