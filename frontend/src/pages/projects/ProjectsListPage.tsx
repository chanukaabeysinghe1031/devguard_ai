import { useState } from "react";
import { FolderKanban, Plus } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { listProjects } from "../../api/projectsApi";
import { queryKeys } from "../../api/queryKeys";
import { DataTable, type DataTableColumn } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorRetryAlert } from "../../components/ui/Alert";
import { LinkButton } from "../../components/ui/LinkButton";
import { PageHeader } from "../../components/ui/PageHeader";
import { SearchInput } from "../../components/ui/SearchInput";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { useAuth } from "../../hooks/useAuth";
import type { ProjectListItem } from "../../types/project";
import { formatRelativeTime, titleCase } from "../../utils/formatters";

export function ProjectsListPage() {
  const [search, setSearch] = useState("");
  const navigate = useNavigate();
  const { hasAnyRole } = useAuth();
  const canWrite = hasAnyRole(["organization_owner", "organization_admin", "engineer"]);

  const params = { page: 1, page_size: 50, search: search || undefined };
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.projects(params),
    queryFn: () => listProjects(params),
  });

  const columns: Array<DataTableColumn<ProjectListItem>> = [
    {
      key: "name",
      header: "Project",
      render: (project) => (
        <div>
          <p className="font-medium text-text-primary">{project.name}</p>
          <p className="text-xs text-text-muted">{project.key}</p>
        </div>
      ),
    },
    {
      key: "ci_provider",
      header: "CI Provider",
      render: (project) => titleCase(project.ci_provider),
    },
    {
      key: "cloud_provider",
      header: "Cloud",
      render: (project) => (project.cloud_provider ? titleCase(project.cloud_provider) : "—"),
    },
    {
      key: "status",
      header: "Status",
      render: (project) => <StatusBadge kind="project" status={project.status} />,
    },
    {
      key: "open_incident_count",
      header: "Open incidents",
      render: (project) => project.open_incident_count,
    },
    {
      key: "last_pipeline_run_at",
      header: "Last pipeline run",
      render: (project) => formatRelativeTime(project.last_pipeline_run_at),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Projects"
        description="Repositories and services connected to DevGuard AI."
        actions={
          canWrite ? (
            <LinkButton to="/projects/new" leftIcon={<Plus className="h-4 w-4" />}>
              New project
            </LinkButton>
          ) : undefined
        }
      />

      <div className="mb-4 max-w-sm">
        <SearchInput value={search} onChange={setSearch} placeholder="Search projects…" />
      </div>

      {isError ? (
        <ErrorRetryAlert message="Failed to load projects." onRetry={() => refetch()} />
      ) : !isLoading && data?.items.length === 0 ? (
        <EmptyState
          icon={FolderKanban}
          title={search ? "No matching projects" : "No projects yet"}
          description={
            search
              ? "Try a different search term."
              : "Create a project to start tracking pipeline runs and incidents."
          }
          action={!search && canWrite && <LinkButton to="/projects/new">Create project</LinkButton>}
        />
      ) : (
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(row) => row.id}
          isLoading={isLoading}
          onRowClick={(row) => navigate(`/projects/${row.id}`)}
        />
      )}
    </div>
  );
}
