import { useQuery } from "@tanstack/react-query";
import { History } from "lucide-react";

import { getIncidentTimeline } from "../../../api/incidentsApi";
import { queryKeys } from "../../../api/queryKeys";
import { EmptyState } from "../../../components/ui/EmptyState";
import { ErrorRetryAlert } from "../../../components/ui/Alert";
import { SkeletonCard } from "../../../components/ui/Skeleton";
import { formatDateTime, titleCase } from "../../../utils/formatters";

export function TimelineTab({ incidentId }: { incidentId: string }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.incidentTimeline(incidentId),
    queryFn: () => getIncidentTimeline(incidentId),
  });

  if (isLoading) return <SkeletonCard />;
  if (isError) return <ErrorRetryAlert message="Failed to load timeline." onRetry={() => refetch()} />;
  if (!data?.items.length) {
    return <EmptyState icon={History} title="No timeline events" description="Incident lifecycle events will appear here." />;
  }

  return (
    <ol className="relative flex flex-col gap-6 border-l border-border pl-5">
      {data.items.map((event) => (
        <li key={event.id} className="relative">
          <span className="absolute -left-[25px] top-1 h-2.5 w-2.5 rounded-full border-2 border-background bg-primary" />
          <p className="text-sm font-medium text-text-primary">{event.title}</p>
          {event.description && <p className="mt-0.5 text-sm text-text-secondary">{event.description}</p>}
          <p className="mt-1 text-xs text-text-muted">
            {formatDateTime(event.occurred_at)} · {titleCase(event.actor_type)}
          </p>
        </li>
      ))}
    </ol>
  );
}
