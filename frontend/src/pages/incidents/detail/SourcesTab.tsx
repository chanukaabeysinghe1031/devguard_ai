import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, ExternalLink } from "lucide-react";

import { getAnalysisSources } from "../../../api/analysesApi";
import { queryKeys } from "../../../api/queryKeys";
import { Badge } from "../../../components/ui/Badge";
import { Card, CardBody } from "../../../components/ui/Card";
import { EmptyState } from "../../../components/ui/EmptyState";
import { ErrorRetryAlert } from "../../../components/ui/Alert";
import { SkeletonCard } from "../../../components/ui/Skeleton";
import { Tooltip } from "../../../components/ui/Tooltip";
import { filterRelevantSources, relevanceBand } from "../../../utils/executionModeLabels";
import { titleCase } from "../../../utils/formatters";

export function SourcesTab({ analysisId }: { analysisId: string | null }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.analysisSources(analysisId ?? ""),
    queryFn: () => getAnalysisSources(analysisId!),
    enabled: Boolean(analysisId),
  });

  const visible = useMemo(() => filterRelevantSources(data?.items ?? []), [data?.items]);
  const hiddenCount = (data?.items.length ?? 0) - visible.length;

  if (!analysisId) {
    return (
      <EmptyState
        icon={BookOpen}
        title="No analysis yet"
        description="Retrieved documentation appears once an analysis has run."
      />
    );
  }

  if (isLoading) return <SkeletonCard />;
  if (isError) return <ErrorRetryAlert message="Failed to load retrieved sources." onRetry={() => refetch()} />;
  if (!visible.length) {
    return (
      <EmptyState
        icon={BookOpen}
        title="No relevant sources"
        description="Grounded knowledge-base sources will appear here when retrieval finds relevant documentation."
      />
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {hiddenCount > 0 && (
        <p className="text-xs text-text-muted">
          Showing {visible.length} relevant sources. {hiddenCount} weak matches were hidden.
        </p>
      )}
      {visible.map((source) => {
        const relevance = relevanceBand(source.similarity_score);
        return (
          <Card key={source.id}>
            <CardBody>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-text-primary">{source.document.title}</p>
                  <p className="text-xs text-text-muted">
                    {source.document.provider}
                    {source.document.technology ? ` · ${source.document.technology}` : ""}
                    {source.document.source_type ? ` · ${titleCase(source.document.source_type)}` : ""}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {source.used_in_reasoning && <Badge tone="success">Used in diagnosis</Badge>}
                  <Tooltip
                    content={
                      source.similarity_score !== null
                        ? `Similarity score: ${(source.similarity_score * 100).toFixed(1)}%`
                        : "Similarity score unavailable"
                    }
                  >
                    <Badge tone={relevance.tone}>{relevance.label}</Badge>
                  </Tooltip>
                </div>
              </div>
              {source.chunk.heading && (
                <p className="mt-2 text-xs font-medium text-text-secondary">{source.chunk.heading}</p>
              )}
              <p className="mt-1 line-clamp-3 text-sm text-text-secondary">{source.chunk.content_preview}</p>
              {source.document.source_url && (
                <a
                  href={source.document.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                >
                  View source <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </CardBody>
          </Card>
        );
      })}
    </div>
  );
}
