import { useMemo } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import { getAnalysisStatus, listIncidentAnalyses } from "../../api/analysesApi";
import { getIncident } from "../../api/incidentsApi";
import { queryKeys } from "../../api/queryKeys";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card, CardBody } from "../../components/ui/Card";
import { PageHeader } from "../../components/ui/PageHeader";
import { Skeleton } from "../../components/ui/Skeleton";
import { ANALYSIS_STAGE_ORDER, getAnalysisStatusMeta } from "../../utils/statusMaps";
import { titleCase } from "../../utils/formatters";

const TERMINAL_STATUSES = new Set(["completed", "failed"]);

export function IncidentAnalysisPage() {
  const { incidentId } = useParams<{ incidentId: string }>();
  const navigate = useNavigate();

  const incidentQuery = useQuery({
    queryKey: queryKeys.incident(incidentId ?? ""),
    queryFn: () => getIncident(incidentId!),
    enabled: Boolean(incidentId),
  });

  const analysesQuery = useQuery({
    queryKey: queryKeys.incidentAnalyses(incidentId ?? ""),
    queryFn: () => listIncidentAnalyses(incidentId!),
    enabled: Boolean(incidentId),
  });

  const latestAnalysisId = useMemo(() => {
    const items = analysesQuery.data ?? [];
    if (items.length === 0) return null;
    return [...items].sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))[0]?.id ?? null;
  }, [analysesQuery.data]);

  const statusQuery = useQuery({
    queryKey: queryKeys.analysisStatus(latestAnalysisId ?? ""),
    queryFn: () => getAnalysisStatus(latestAnalysisId!),
    enabled: Boolean(latestAnalysisId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && TERMINAL_STATUSES.has(status) ? false : 2500;
    },
  });

  const isTerminal = statusQuery.data ? TERMINAL_STATUSES.has(statusQuery.data.status) : false;

  if (!latestAnalysisId && analysesQuery.isLoading) {
    return <Skeleton className="h-64 w-full max-w-2xl" />;
  }

  if (!latestAnalysisId) {
    return (
      <Alert variant="warning" title="No analysis found">
        No analysis run was found for this incident yet.
      </Alert>
    );
  }

  const status = statusQuery.data;
  const meta = getAnalysisStatusMeta(status?.status);

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="Analysis in progress"
        description={incidentQuery.data ? incidentQuery.data.title : "Loading incident…"}
      />

      <Card>
        <CardBody>
          <div className="flex items-center gap-3">
            {status?.status === "failed" ? (
              <AlertTriangle className="h-8 w-8 text-danger" />
            ) : status?.status === "completed" ? (
              <CheckCircle2 className="h-8 w-8 text-success" />
            ) : (
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            )}
            <div>
              <p className="text-base font-semibold text-text-primary">{meta.label}</p>
              <p className="text-sm text-text-muted">
                {status?.current_stage ? titleCase(status.current_stage) : "Waiting to start…"}
              </p>
            </div>
          </div>

          <div className="mt-5 h-2 w-full overflow-hidden rounded-full bg-surface-interactive">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${status?.progress_percentage ?? 0}%` }}
            />
          </div>
          <p className="mt-1.5 text-right text-xs text-text-muted">{status?.progress_percentage ?? 0}%</p>

          <ol className="mt-6 flex flex-col gap-2">
            {ANALYSIS_STAGE_ORDER.map((stage) => {
              const stageIndex = ANALYSIS_STAGE_ORDER.indexOf(stage);
              const currentIndex = status?.current_stage
                ? ANALYSIS_STAGE_ORDER.indexOf(status.current_stage)
                : -1;
              const isDone =
                isTerminal && status?.status === "completed" ? true : stageIndex < currentIndex;
              const isActive = stage === status?.current_stage;
              return (
                <li key={stage} className="flex items-center gap-2 text-sm">
                  <span
                    className={
                      isDone
                        ? "h-2 w-2 rounded-full bg-success"
                        : isActive
                          ? "h-2 w-2 rounded-full bg-primary"
                          : "h-2 w-2 rounded-full bg-surface-interactive"
                    }
                  />
                  <span className={isActive ? "text-text-primary" : "text-text-muted"}>{titleCase(stage)}</span>
                </li>
              );
            })}
          </ol>

          {status?.status === "failed" && (
            <Alert variant="danger" className="mt-5">
              The analysis failed. You can review partial results or retry from the incident page.
            </Alert>
          )}

          <div className="mt-6 flex justify-end gap-2">
            {isTerminal ? (
              <Button onClick={() => navigate(`/incidents/${incidentId}`)}>View incident</Button>
            ) : (
              <Button variant="ghost" onClick={() => navigate(`/incidents/${incidentId}`)}>
                View incident in background
              </Button>
            )}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
