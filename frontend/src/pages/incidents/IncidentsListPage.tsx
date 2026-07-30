import { useMemo, useState } from "react";
import { Activity, ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { listIncidents } from "../../api/incidentsApi";
import { listProjects } from "../../api/projectsApi";
import { queryKeys } from "../../api/queryKeys";
import { Button } from "../../components/ui/Button";
import { DataTable, type DataTableColumn } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorRetryAlert } from "../../components/ui/Alert";
import { LinkButton } from "../../components/ui/LinkButton";
import { PageHeader } from "../../components/ui/PageHeader";
import { SearchInput } from "../../components/ui/SearchInput";
import { Select } from "../../components/ui/Select";
import { SeverityBadge } from "../../components/ui/SeverityBadge";
import { StatusBadge } from "../../components/ui/StatusBadge";
import type { IncidentListItem } from "../../types/incident";
import { formatRelativeTime } from "../../utils/formatters";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "detected", label: "Detected" },
  { value: "analysing", label: "Analysing" },
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "resolved", label: "Resolved" },
  { value: "closed", label: "Closed" },
  { value: "analysis_failed", label: "Analysis failed" },
  { value: "reopened", label: "Reopened" },
];

const SEVERITY_OPTIONS = [
  { value: "", label: "All severities" },
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

const PAGE_SIZE = 20;

export function IncidentsListPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [projectId, setProjectId] = useState("");
  const [page, setPage] = useState(1);

  const projectsQuery = useQuery({
    queryKey: queryKeys.projects({ page: 1, page_size: 100 }),
    queryFn: () => listProjects({ page: 1, page_size: 100 }),
  });

  const params = useMemo(
    () => ({
      page,
      page_size: PAGE_SIZE,
      search: search || undefined,
      status: status || undefined,
      severity: severity || undefined,
      project_id: projectId || undefined,
    }),
    [page, search, status, severity, projectId],
  );

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.incidents(params),
    queryFn: () => listIncidents(params),
  });

  const projectOptions = [
    { value: "", label: "All projects" },
    ...(projectsQuery.data?.items.map((project) => ({ value: project.id, label: project.name })) ?? []),
  ];

  const columns: Array<DataTableColumn<IncidentListItem>> = [
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
    { key: "project", header: "Project", render: (incident) => incident.project.name },
    { key: "severity", header: "Severity", render: (incident) => <SeverityBadge severity={incident.severity} /> },
    { key: "status", header: "Status", render: (incident) => <StatusBadge kind="incident" status={incident.status} /> },
    {
      key: "category",
      header: "Predicted category",
      render: (incident) => incident.predicted_category ?? "—",
    },
    { key: "detected_at", header: "Detected", render: (incident) => formatRelativeTime(incident.detected_at) },
  ];

  const hasFilters = Boolean(search || status || severity || projectId);
  const totalPages = data?.total_pages ?? 1;

  return (
    <div>
      <PageHeader
        title="Incidents"
        description="All CI/CD and deployment incidents detected across your organization."
        actions={
          <LinkButton to="/incidents/new" leftIcon={<Plus className="h-4 w-4" />}>
            New incident
          </LinkButton>
        }
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <SearchInput
          value={search}
          onChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
          placeholder="Search incidents…"
          className="sm:w-64"
        />
        <Select
          options={projectOptions}
          value={projectId}
          onChange={(event) => {
            setProjectId(event.target.value);
            setPage(1);
          }}
          className="sm:w-48"
        />
        <Select
          options={STATUS_OPTIONS}
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
          className="sm:w-44"
        />
        <Select
          options={SEVERITY_OPTIONS}
          value={severity}
          onChange={(event) => {
            setSeverity(event.target.value);
            setPage(1);
          }}
          className="sm:w-44"
        />
      </div>

      {isError ? (
        <ErrorRetryAlert message="Failed to load incidents." onRetry={() => refetch()} />
      ) : !isLoading && data?.items.length === 0 ? (
        <EmptyState
          icon={Activity}
          title={hasFilters ? "No matching incidents" : "No incidents yet"}
          description={
            hasFilters
              ? "Try adjusting your filters."
              : "Incidents will appear here once a pipeline run fails or one is created manually."
          }
          action={!hasFilters && <LinkButton to="/incidents/new">Create incident</LinkButton>}
        />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            rowKey={(row) => row.id}
            isLoading={isLoading}
            onRowClick={(row) => navigate(`/incidents/${row.id}`)}
          />
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between text-sm text-text-muted">
              <span>
                Page {data?.page ?? page} of {totalPages} · {data?.total_items ?? 0} incidents
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  leftIcon={<ChevronLeft className="h-4 w-4" />}
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  rightIcon={<ChevronRight className="h-4 w-4" />}
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
