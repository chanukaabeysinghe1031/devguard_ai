import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  Crosshair,
  Gauge,
  Percent,
  Target,
  Timer,
} from "lucide-react";

import { getLatestEvaluationMetrics } from "../../api/evaluationApi";
import { Alert, ErrorRetryAlert } from "../../components/ui/Alert";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { MetricCard } from "../../components/ui/MetricCard";
import { PageHeader } from "../../components/ui/PageHeader";
import { SkeletonCard } from "../../components/ui/Skeleton";
import { formatNumber, formatPercentage } from "../../utils/formatters";

export function EvaluationPage() {
  const metricsQuery = useQuery({
    queryKey: ["evaluation", "latest-metrics"],
    queryFn: getLatestEvaluationMetrics,
    retry: false,
  });

  const metrics = metricsQuery.data?.aggregate_metrics;

  return (
    <div>
      <PageHeader
        title="Evaluation"
        description="Versioned research metrics from the retrieval and classification benchmark suite. Separate from operational dashboard KPIs."
      />

      {metricsQuery.isLoading ? (
        <div className="grid gap-4 md:grid-cols-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : metricsQuery.isError ? (
        <ErrorRetryAlert
          message="Evaluation metrics are unavailable. Run the benchmark CLI to generate latest_metrics.json."
          onRetry={() => metricsQuery.refetch()}
        />
      ) : !metrics ? (
        <EmptyState
          icon={BarChart3}
          title="No evaluation run found"
          description="Research evaluation metrics will appear after a benchmark run writes datasets/benchmark/results/latest_metrics.json."
        />
      ) : (
        <div className="flex flex-col gap-6">
          <Alert variant="info">
            Dataset/run: {metricsQuery.data?.run_dir ?? "—"} · Labels:{" "}
            {metricsQuery.data?.labels_mode ?? "—"} · Version:{" "}
            {metricsQuery.data?.benchmark_version ?? "—"}
          </Alert>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Precision@5"
              value={formatPercentage(metrics["precision@5"], 1)}
              icon={Percent}
              tone="primary"
            />
            <MetricCard
              label="Recall@10"
              value={formatPercentage(metrics["recall@10"], 1)}
              icon={Target}
              tone="info"
            />
            <MetricCard
              label="nDCG@10"
              value={formatPercentage(metrics["ndcg@10"], 1)}
              icon={Gauge}
              tone="success"
            />
            <MetricCard
              label="MRR"
              value={formatPercentage(metrics.mrr, 1)}
              icon={Crosshair}
              tone="secondary"
            />
            <MetricCard
              label="MAP"
              value={formatPercentage(metrics.map, 1)}
              icon={BarChart3}
              tone="primary"
            />
            <MetricCard
              label="Hit rate"
              value={formatPercentage(metrics.hit_rate, 1)}
              icon={Target}
              tone="success"
            />
            <MetricCard
              label="Category accuracy"
              value={formatPercentage(metrics.category_accuracy, 1)}
              icon={Percent}
              tone="warning"
            />
            <MetricCard
              label="Latency (ms)"
              value={formatNumber(metrics.latency_ms)}
              icon={Timer}
              tone="info"
            />
          </div>

          <Card>
            <CardHeader title="Limitations" />
            <CardBody>
              <p className="text-sm text-text-secondary">
                These metrics come from the frozen research benchmark corpus and gold labels. They measure
                retrieval and classification quality for the dissertation evaluation, not live operational
                incident success rates.
              </p>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  );
}
