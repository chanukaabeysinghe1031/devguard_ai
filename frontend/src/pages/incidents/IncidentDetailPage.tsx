import { useMemo } from "react";
import { RefreshCcw } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { reanalyseIncident } from "../../api/analysesApi";
import { ApiError } from "../../api/client";
import { acknowledgeIncident, getIncident } from "../../api/incidentsApi";
import { queryKeys } from "../../api/queryKeys";
import { Alert, ErrorRetryAlert } from "../../components/ui/Alert";
import { Breadcrumbs } from "../../components/ui/Breadcrumbs";
import { Button } from "../../components/ui/Button";
import { PageHeader } from "../../components/ui/PageHeader";
import { SeverityBadge } from "../../components/ui/SeverityBadge";
import { Skeleton } from "../../components/ui/Skeleton";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { Tabs } from "../../components/ui/Tabs";
import { EvidenceTab } from "./detail/EvidenceTab";
import { FilesTab } from "./detail/FilesTab";
import { GitHubContextCard } from "./detail/GitHubContextCard";
import { NotesTab } from "./detail/NotesTab";
import { OverviewTab } from "./detail/OverviewTab";
import { RecommendationsTab } from "./detail/RecommendationsTab";
import { ReportTab } from "./detail/ReportTab";
import { ResolutionTab } from "./detail/ResolutionTab";
import { SourcesTab } from "./detail/SourcesTab";
import { TimelineTab } from "./detail/TimelineTab";

const TAB_ITEMS = [
  { id: "overview", label: "Overview" },
  { id: "evidence", label: "Evidence" },
  { id: "sources", label: "Sources" },
  { id: "recommendations", label: "Recommendations" },
  { id: "timeline", label: "Timeline" },
  { id: "notes", label: "Notes" },
  { id: "files", label: "Files" },
  { id: "resolution", label: "Resolution" },
  { id: "report", label: "Report" },
];

export function IncidentDetailPage() {
  const { incidentId } = useParams<{ incidentId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const activeTab = searchParams.get("tab") ?? "overview";

  const incidentQuery = useQuery({
    queryKey: queryKeys.incident(incidentId ?? ""),
    queryFn: () => getIncident(incidentId!),
    enabled: Boolean(incidentId),
  });

  const analysisId = useMemo(() => incidentQuery.data?.latest_analysis?.id ?? null, [incidentQuery.data]);

  const acknowledgeMutation = useMutation({
    mutationFn: () => acknowledgeIncident(incidentId!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.incident(incidentId ?? "") }),
  });

  const reanalyseMutation = useMutation({
    mutationFn: () => reanalyseIncident(incidentId!, { reason: "Manual re-analysis requested from incident detail" }),
    onSuccess: () => navigate(`/incidents/${incidentId}/analysis`),
  });

  const setTab = (tab: string) => setSearchParams((prev) => ({ ...Object.fromEntries(prev), tab }), { replace: true });

  if (incidentQuery.isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-10 w-96" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (incidentQuery.isError || !incidentQuery.data) {
    return <ErrorRetryAlert message="Failed to load incident." onRetry={() => incidentQuery.refetch()} />;
  }

  const incident = incidentQuery.data;

  return (
    <div>
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-2">
            {incident.title}
            <SeverityBadge severity={incident.severity} />
            <StatusBadge kind="incident" status={incident.status} />
          </span>
        }
        breadcrumbs={
          <Breadcrumbs
            items={[
              { label: "Incidents", to: "/incidents" },
              { label: incident.incident_number },
            ]}
          />
        }
        description={
          <Link to={`/projects/${incident.project.id}`} className="hover:underline">
            {incident.project.name}
          </Link>
        }
        actions={
          <>
            {!incident.acknowledged_at && (
              <Button variant="outline" onClick={() => acknowledgeMutation.mutate()} isLoading={acknowledgeMutation.isPending}>
                Acknowledge
              </Button>
            )}
            <Button
              variant="outline"
              leftIcon={<RefreshCcw className="h-4 w-4" />}
              onClick={() => reanalyseMutation.mutate()}
              isLoading={reanalyseMutation.isPending}
            >
              Re-analyse
            </Button>
          </>
        }
      />

      {reanalyseMutation.isError && (
        <Alert variant="danger" className="mb-4">
          {reanalyseMutation.error instanceof ApiError ? reanalyseMutation.error.message : "Failed to start re-analysis."}
        </Alert>
      )}

      <GitHubContextCard pipelineRunId={incident.pipeline_run_id} />

      <Tabs items={TAB_ITEMS} activeId={activeTab} onChange={setTab} />

      <div className="mt-5">
        {activeTab === "overview" && <OverviewTab incident={incident} analysisId={analysisId} />}
        {activeTab === "evidence" && <EvidenceTab analysisId={analysisId} />}
        {activeTab === "sources" && <SourcesTab analysisId={analysisId} />}
        {activeTab === "recommendations" && <RecommendationsTab analysisId={analysisId} />}
        {activeTab === "timeline" && <TimelineTab incidentId={incident.id} />}
        {activeTab === "notes" && <NotesTab incidentId={incident.id} />}
        {activeTab === "files" && <FilesTab incidentId={incident.id} />}
        {activeTab === "resolution" && <ResolutionTab incident={incident} incidentId={incident.id} />}
        {activeTab === "report" && <ReportTab incidentId={incident.id} />}
      </div>
    </div>
  );
}
