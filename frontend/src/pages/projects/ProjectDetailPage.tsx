import { useState } from "react";
import { Archive, Pencil, Plug, RotateCcw } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import { archiveProject, getProject, restoreProject } from "../../api/projectsApi";
import { listIncidents } from "../../api/incidentsApi";
import { listPipelineRuns } from "../../api/pipelineRunsApi";
import { queryKeys } from "../../api/queryKeys";
import { ApiError } from "../../api/client";
import { ErrorRetryAlert } from "../../components/ui/Alert";
import { Breadcrumbs } from "../../components/ui/Breadcrumbs";
import { Button } from "../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { DataTable, type DataTableColumn } from "../../components/ui/DataTable";
import { LinkButton } from "../../components/ui/LinkButton";
import { PageHeader } from "../../components/ui/PageHeader";
import { SeverityBadge } from "../../components/ui/SeverityBadge";
import { Skeleton } from "../../components/ui/Skeleton";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { Tabs } from "../../components/ui/Tabs";
import type { IncidentListItem } from "../../types/incident";
import type { PipelineRun } from "../../types/pipelineRun";
import { formatDate, formatRelativeTime, titleCase } from "../../utils/formatters";

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"incidents" | "pipeline-runs">("incidents");
  const [confirmArchive, setConfirmArchive] = useState(false);

  const projectQuery = useQuery({
    queryKey: queryKeys.project(projectId ?? ""),
    queryFn: () => getProject(projectId!),
    enabled: Boolean(projectId),
  });

  const incidentsQuery = useQuery({
    queryKey: queryKeys.incidents({ project_id: projectId, page: 1, page_size: 20 }),
    queryFn: () => listIncidents({ project_id: projectId, page: 1, page_size: 20 }),
    enabled: Boolean(projectId) && activeTab === "incidents",
  });

  const pipelineRunsQuery = useQuery({
    queryKey: queryKeys.pipelineRuns(projectId ?? "", { page: 1, page_size: 20 }),
    queryFn: () => listPipelineRuns(projectId!, { page: 1, page_size: 20 }),
    enabled: Boolean(projectId) && activeTab === "pipeline-runs",
  });

  const archiveMutation = useMutation({
    mutationFn: () =>
      projectQuery.data?.status === "archived" ? restoreProject(projectId!) : archiveProject(projectId!),
    onSuccess: async () => {
      setConfirmArchive(false);
      await queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId ?? "") });
    },
  });

  const incidentColumns: Array<DataTableColumn<IncidentListItem>> = [
    {
      key: "title",
      header: "Incident",
      render: (incident) => (
        <div>
          <p className="font-medium text-text-primary">{incident.title}</p>
          <p className="text-xs text-text-muted">{incident.incident_number}</p>
        </div>
      ),
    },
    { key: "severity", header: "Severity", render: (incident) => <SeverityBadge severity={incident.severity} /> },
    { key: "status", header: "Status", render: (incident) => <StatusBadge kind="incident" status={incident.status} /> },
    { key: "detected_at", header: "Detected", render: (incident) => formatRelativeTime(incident.detected_at) },
  ];

  const pipelineColumns: Array<DataTableColumn<PipelineRun>> = [
    {
      key: "workflow_name",
      header: "Workflow",
      render: (run) => (
        <div>
          <p className="font-medium text-text-primary">{run.workflow_name ?? run.external_run_id ?? "Pipeline run"}</p>
          <p className="text-xs text-text-muted">{run.branch ?? "—"}</p>
        </div>
      ),
    },
    { key: "status", header: "Status", render: (run) => <StatusBadge kind="pipeline" status={run.status} /> },
    { key: "environment", header: "Environment", render: (run) => run.environment ?? "—" },
    { key: "incident_count", header: "Incidents", render: (run) => run.incident_count },
    { key: "started_at", header: "Started", render: (run) => formatRelativeTime(run.started_at) },
  ];

  if (projectQuery.isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (projectQuery.isError || !projectQuery.data) {
    return <ErrorRetryAlert message="Failed to load project." onRetry={() => projectQuery.refetch()} />;
  }

  const project = projectQuery.data;

  return (
    <div>
      <PageHeader
        title={project.name}
        breadcrumbs={<Breadcrumbs items={[{ label: "Projects", to: "/projects" }, { label: project.name }]} />}
        description={project.description || `${titleCase(project.ci_provider)} project · key ${project.key}`}
        actions={
          <>
            <LinkButton
              to={`/projects/${project.id}/integrations`}
              variant="outline"
              leftIcon={<Plug className="h-4 w-4" />}
            >
              Integrations
            </LinkButton>
            <LinkButton to={`/projects/${project.id}/edit`} variant="outline" leftIcon={<Pencil className="h-4 w-4" />}>
              Edit
            </LinkButton>
            <Button
              variant={project.status === "archived" ? "primary" : "danger"}
              leftIcon={project.status === "archived" ? <RotateCcw className="h-4 w-4" /> : <Archive className="h-4 w-4" />}
              onClick={() => setConfirmArchive(true)}
            >
              {project.status === "archived" ? "Restore" : "Archive"}
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardBody>
            <p className="text-xs font-medium uppercase tracking-wide text-text-muted">Pipeline runs</p>
            <p className="mt-1 text-2xl font-bold text-text-primary">{project.statistics.total_pipeline_runs}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <p className="text-xs font-medium uppercase tracking-wide text-text-muted">Failed runs</p>
            <p className="mt-1 text-2xl font-bold text-danger">{project.statistics.failed_pipeline_runs}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <p className="text-xs font-medium uppercase tracking-wide text-text-muted">Open incidents</p>
            <p className="mt-1 text-2xl font-bold text-warning">{project.statistics.open_incidents}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <p className="text-xs font-medium uppercase tracking-wide text-text-muted">Resolved incidents</p>
            <p className="mt-1 text-2xl font-bold text-success">{project.statistics.resolved_incidents}</p>
          </CardBody>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader
          title="Project details"
          subtitle={`Created ${formatDate(project.created_at)}`}
        />
        <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-text-muted">Repository</p>
            <p className="mt-0.5 text-sm text-text-primary">
              {project.repository_url ? (
                <a href={project.repository_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                  {project.repository_url}
                </a>
              ) : (
                "—"
              )}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-text-muted">Default branch</p>
            <p className="mt-0.5 text-sm text-text-primary">{project.default_branch ?? "—"}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-text-muted">Cloud provider</p>
            <p className="mt-0.5 text-sm text-text-primary">
              {project.cloud_provider ? titleCase(project.cloud_provider) : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-text-muted">Default environment</p>
            <p className="mt-0.5 text-sm text-text-primary">
              {project.default_environment ? titleCase(project.default_environment) : "—"}
            </p>
          </div>
        </CardBody>
      </Card>

      <div className="mt-6">
        <Tabs
          items={[
            { id: "incidents", label: "Incidents" },
            { id: "pipeline-runs", label: "Pipeline runs" },
          ]}
          activeId={activeTab}
          onChange={(id) => setActiveTab(id as typeof activeTab)}
        />
        <div className="mt-4">
          {activeTab === "incidents" ? (
            <DataTable
              columns={incidentColumns}
              rows={incidentsQuery.data?.items ?? []}
              rowKey={(row) => row.id}
              isLoading={incidentsQuery.isLoading}
              emptyTitle="No incidents for this project"
              emptyDescription="Incidents detected for this project will appear here."
              onRowClick={(row) => navigate(`/incidents/${row.id}`)}
            />
          ) : (
            <DataTable
              columns={pipelineColumns}
              rows={pipelineRunsQuery.data?.items ?? []}
              rowKey={(row) => row.id}
              isLoading={pipelineRunsQuery.isLoading}
              emptyTitle="No pipeline runs recorded"
              emptyDescription="Pipeline run history for this project will appear here."
              onRowClick={(row) => navigate(`/pipeline-runs/${row.id}`)}
            />
          )}
        </div>
      </div>

      <ConfirmDialog
        isOpen={confirmArchive}
        title={project.status === "archived" ? "Restore project?" : "Archive project?"}
        description={
          project.status === "archived"
            ? "This project will become active again."
            : "Archived projects are hidden from active views but not deleted."
        }
        confirmLabel={project.status === "archived" ? "Restore" : "Archive"}
        isDangerous={project.status !== "archived"}
        isLoading={archiveMutation.isPending}
        onConfirm={() => archiveMutation.mutate()}
        onCancel={() => setConfirmArchive(false)}
      />

      {archiveMutation.isError && (
        <div className="mt-4">
          <ErrorRetryAlert
            message={archiveMutation.error instanceof ApiError ? archiveMutation.error.message : "Action failed."}
          />
        </div>
      )}
    </div>
  );
}
