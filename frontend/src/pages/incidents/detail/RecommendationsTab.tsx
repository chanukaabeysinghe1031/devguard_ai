import { useQuery } from "@tanstack/react-query";
import { Lightbulb } from "lucide-react";

import { getAnalysisRecommendations } from "../../../api/analysesApi";
import { queryKeys } from "../../../api/queryKeys";
import { Badge } from "../../../components/ui/Badge";
import { Card, CardBody } from "../../../components/ui/Card";
import { EmptyState } from "../../../components/ui/EmptyState";
import { ErrorRetryAlert } from "../../../components/ui/Alert";
import { SkeletonCard } from "../../../components/ui/Skeleton";
import { uniqueRecommendationText } from "../../../utils/executionModeLabels";
import { titleCase } from "../../../utils/formatters";
import { getIncidentPriorityMeta } from "../../../utils/statusMaps";

export function RecommendationsTab({ analysisId }: { analysisId: string | null }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.analysisRecommendations(analysisId ?? ""),
    queryFn: () => getAnalysisRecommendations(analysisId!),
    enabled: Boolean(analysisId),
  });

  if (!analysisId) {
    return <EmptyState icon={Lightbulb} title="No analysis yet" description="Recommendations appear once an analysis has run." />;
  }

  if (isLoading) return <SkeletonCard />;
  if (isError) return <ErrorRetryAlert message="Failed to load recommendations." onRetry={() => refetch()} />;
  if (!data?.items.length) {
    return <EmptyState icon={Lightbulb} title="No recommendations yet" description="AI recommendations will appear here." />;
  }

  return (
    <div className="flex flex-col gap-4">
      {data.summary && (
        <Card>
          <CardBody>
            <p className="text-xs font-medium uppercase tracking-wide text-text-muted">Summary</p>
            <p className="mt-1 text-sm text-text-secondary">{data.summary}</p>
          </CardBody>
        </Card>
      )}
      <div className="flex flex-col gap-3">
        {data.items
          .sort((a, b) => a.step_number - b.step_number)
          .map((item) => {
            const riskMeta = getIncidentPriorityMeta(item.risk_level ?? undefined);
            return (
              <Card key={item.id}>
                <CardBody>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
                        {item.step_number}
                      </span>
                      <p className="text-sm font-semibold text-text-primary">{item.title}</p>
                    </div>
                    {item.risk_level && <Badge tone={riskMeta.tone}>{titleCase(item.risk_level)} risk</Badge>}
                  </div>
                  {uniqueRecommendationText(item.action, item.explanation).map((text, idx) => (
                    <p
                      key={`${item.id}-text-${idx}`}
                      className={idx === 0 ? "mt-2 text-sm text-text-secondary" : "mt-1.5 text-xs text-text-muted"}
                    >
                      {text}
                    </p>
                  ))}
                  {item.expected_result && (
                    <p className="mt-2 text-xs text-text-secondary">
                      <span className="font-medium text-text-muted">Expected result: </span>
                      {item.expected_result}
                    </p>
                  )}
                </CardBody>
              </Card>
            );
          })}
      </div>
    </div>
  );
}
