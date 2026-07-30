import { Github } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { getPipelineRun } from "../../api/pipelineRunsApi";
import { listIncidents } from "../../api/incidentsApi";
import { queryKeys } from "../../api/queryKeys";
import { ErrorRetryAlert } from "../../components/ui/Alert";
import { Badge } from "../../components/ui/Badge";
import { Breadcrumbs } from "../../components/ui/Breadcrumbs";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { DataTable, type DataTableColumn } from "../../components/ui/DataTable";
import { KeyValueList } from "../../components/ui/KeyValueList";
import { PageHeader } from "../../components/ui/PageHeader";
import { SeverityBadge } from "../../components/ui/SeverityBadge";
import { Skeleton } from "../../components/ui/Skeleton";
import { StatusBadge } from "../../components/ui/StatusBadge";
import type { IncidentListItem } from "../../types/incident";
import { formatDateTime, formatDurationMs, titleCase } from "../../utils/formatters";
import { isSafeGitHubUrl } from "../../utils/githubUrl";

export function PipelineRunDetailPage() {
  const { pipelineRunId } = useParams<{ pipelineRunId: string }>();

  const runQuery = useQuery({
    queryKey: queryKeys.pipelineRun(pipelineRunId ?? ""),
    queryFn: () => getPipelineRun(pipelineRunId!),
    enabled: Boolean(pipelineRunId),
  });

  const incidentsQuery = useQuery({
    queryKey: queryKeys.incidents({ pipeline_run_id: pipelineRunId, page: 1, page_size: 20 }),
    queryFn: () => listIncidents({ pipeline_run_id: pipelineRunId, page: 1, page_size: 20 }),
    enabled: Boolean(pipelineRunId),
  });

  const columns: Array<DataTableColumn<IncidentListItem>> = [
    { key: "title", header: "Incident", render: (incident) => incident.title },
    { key: "severity", header: "Severity", render: (incident) => <SeverityBadge severity={incident.severity} /> },
    { key: "status", header: "Status", render: (incident) => <StatusBadge kind="incident" status={incident.status} /> },
  ];

  if (runQuery.isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (runQuery.isError || !runQuery.data) {
    return <ErrorRetryAlert message="Failed to load pipeline run." onRetry={() => runQuery.refetch()} />;
  }

  const run = runQuery.data;
  const isGithub = run.provider === "github_actions";
  const showSourceLink = isGithub ? isSafeGitHubUrl(run.source_url) : Boolean(run.source_url);

  return (
    <div>
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-2">
            {run.workflow_name ?? run.external_run_id ?? "Pipeline run"}
            {isGithub && (
              <Badge tone="neutral">
                <Github className="h-3 w-3" /> GitHub
              </Badge>
            )}
          </span>
        }
        breadcrumbs={<Breadcrumbs items={[{ label: "Projects", to: "/projects" }, { label: "Pipeline run" }]} />}
        description={
          <Link to={`/projects/${run.project_id}`} className="hover:underline">
            View project
          </Link>
        }
      />

      <Card>
        <CardHeader title="Run details" action={<StatusBadge kind="pipeline" status={run.status} />} />
        <CardBody>
          <KeyValueList
            columns={2}
            items={[
              { label: "Provider", value: titleCase(run.provider) },
              { label: "Branch", value: run.branch ?? "—" },
              { label: "Commit", value: run.commit_sha ?? "—" },
              { label: "Environment", value: run.environment ? titleCase(run.environment) : "—" },
              { label: "Triggered by", value: run.triggered_by ?? "—" },
              { label: "Started", value: formatDateTime(run.started_at) },
              { label: "Completed", value: formatDateTime(run.completed_at) },
              {
                label: "Duration",
                value: run.duration_seconds !== null ? formatDurationMs(run.duration_seconds * 1000) : "—",
              },
            ]}
          />
          {showSourceLink && run.source_url && (
            <a
              href={run.source_url}
              target="_blank"
              rel="noreferrer"
              className="mt-4 inline-block text-sm text-primary hover:underline"
            >
              {isGithub ? "View run on GitHub" : "View in CI provider"}
            </a>
          )}
        </CardBody>
      </Card>

      <Card className="mt-6">
        <CardHeader title="Related incidents" />
        <CardBody className="!p-0">
          <DataTable
            columns={columns}
            rows={incidentsQuery.data?.items ?? []}
            rowKey={(row) => row.id}
            isLoading={incidentsQuery.isLoading}
            emptyTitle="No incidents linked"
            emptyDescription="No incidents have been linked to this pipeline run."
          />
        </CardBody>
      </Card>
    </div>
  );
}
