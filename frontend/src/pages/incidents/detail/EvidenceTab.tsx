import { useQuery } from "@tanstack/react-query";
import { FileSearch } from "lucide-react";

import { getAnalysisEvidence } from "../../../api/analysesApi";
import { queryKeys } from "../../../api/queryKeys";
import { Card, CardBody } from "../../../components/ui/Card";
import { EmptyState } from "../../../components/ui/EmptyState";
import { ErrorRetryAlert } from "../../../components/ui/Alert";
import { Badge } from "../../../components/ui/Badge";
import { SkeletonCard } from "../../../components/ui/Skeleton";
import { titleCase } from "../../../utils/formatters";

export function EvidenceTab({ analysisId }: { analysisId: string | null }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.analysisEvidence(analysisId ?? ""),
    queryFn: () => getAnalysisEvidence(analysisId!),
    enabled: Boolean(analysisId),
  });

  if (!analysisId) {
    return <EmptyState icon={FileSearch} title="No analysis yet" description="Evidence appears once an analysis has run." />;
  }

  if (isLoading) return <SkeletonCard />;
  if (isError) return <ErrorRetryAlert message="Failed to load evidence." onRetry={() => refetch()} />;
  if (!data?.items.length) {
    return (
      <EmptyState
        icon={FileSearch}
        title="No evidence extracted"
        description="The analysis did not extract any supporting evidence."
      />
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {data.items.map((item) => (
        <Card key={item.id}>
          <CardBody>
            <div className="flex items-center justify-between gap-2">
              <Badge tone="info">{titleCase(item.evidence_type)}</Badge>
              {item.importance_score !== null && (
                <span className="text-xs text-text-muted">Importance {(item.importance_score * 100).toFixed(0)}%</span>
              )}
            </div>
            {item.source_file?.name && (
              <p className="mt-2 text-xs text-text-muted">
                {item.source_file.name}
                {item.line_start !== null && item.line_end !== null && ` · lines ${item.line_start}-${item.line_end}`}
              </p>
            )}
            {item.excerpt && (
              <pre className="mt-2 overflow-x-auto rounded-md bg-[#0a0f1a] p-3 text-xs text-text-secondary">
                {item.excerpt}
              </pre>
            )}
            {item.explanation && <p className="mt-2 text-sm text-text-secondary">{item.explanation}</p>}
          </CardBody>
        </Card>
      ))}
    </div>
  );
}
