import type { ReactNode } from "react";
import { CloudCog, Github, UploadCloud, type LucideIcon } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { listProjectIntegrations } from "../../api/integrationsApi";
import { getProject } from "../../api/projectsApi";
import { queryKeys } from "../../api/queryKeys";
import { ErrorRetryAlert } from "../../components/ui/Alert";
import { Badge } from "../../components/ui/Badge";
import { Breadcrumbs } from "../../components/ui/Breadcrumbs";
import { Card, CardBody } from "../../components/ui/Card";
import { LinkButton } from "../../components/ui/LinkButton";
import { PageHeader } from "../../components/ui/PageHeader";
import { Skeleton } from "../../components/ui/Skeleton";
import { useAuth } from "../../hooks/useAuth";
import type { ProjectIntegrationSummary } from "../../types/integration";
import { formatRelativeTime } from "../../utils/formatters";
import type { BadgeTone } from "../../utils/statusMaps";

const ADMIN_ROLES = ["organization_owner", "organization_admin"] as const;

const STATUS_BADGE: Record<string, BadgeTone> = {
  connected: "success",
  paused: "warning",
  not_connected: "neutral",
  coming_later: "neutral",
};

const STATUS_LABEL: Record<string, string> = {
  connected: "Connected",
  paused: "Paused",
  not_connected: "Not connected",
  coming_later: "Coming later",
};

/** Providers not yet returned by the backend list-integrations endpoint (frontend placeholder only). */
const FRONTEND_ONLY_DEFERRED: Array<{ provider: string; display_name: string }> = [
  { provider: "aws_eventbridge", display_name: "AWS EventBridge" },
];

function IntegrationCard({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <Card>
      <CardBody className="flex flex-col gap-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-surface-interactive">
            <Icon className="h-5 w-5 text-text-secondary" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-text-primary">{title}</h3>
            <p className="mt-0.5 text-sm text-text-muted">{description}</p>
          </div>
        </div>
        {children}
      </CardBody>
    </Card>
  );
}

function GitHubCard({ projectId, summary, canManage }: { projectId: string; summary?: ProjectIntegrationSummary; canManage: boolean }) {
  const status = summary?.status ?? "not_connected";
  const connection = summary?.connection ?? null;

  return (
    <IntegrationCard
      icon={Github}
      title="GitHub Actions"
      description="Automatically ingest failed workflow runs and open incidents for this project."
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={STATUS_BADGE[status] ?? "neutral"} dot>
          {STATUS_LABEL[status] ?? status}
        </Badge>
        {summary?.available === false && <Badge tone="neutral">Not configured</Badge>}
      </div>

      {connection && (
        <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-sm">
          <div className="flex justify-between gap-2">
            <dt className="text-text-muted">Repository</dt>
            <dd className="truncate text-text-primary">{connection.repository_full_name}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-text-muted">Last event</dt>
            <dd className="text-text-primary">{formatRelativeTime(connection.last_webhook_at)}</dd>
          </div>
        </dl>
      )}

      <div className="flex items-center gap-2">
        {canManage ? (
          <LinkButton to={`/projects/${projectId}/integrations/github`} variant={connection ? "outline" : "primary"} size="sm">
            {connection ? "Configure" : "Connect"}
          </LinkButton>
        ) : (
          <Link to={`/projects/${projectId}/integrations/github`} className="text-sm text-primary hover:underline">
            View details
          </Link>
        )}
      </div>
    </IntegrationCard>
  );
}

export function ProjectIntegrationsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { hasAnyRole } = useAuth();
  const canManage = hasAnyRole([...ADMIN_ROLES]);

  const projectQuery = useQuery({
    queryKey: queryKeys.project(projectId ?? ""),
    queryFn: () => getProject(projectId!),
    enabled: Boolean(projectId),
  });

  const integrationsQuery = useQuery({
    queryKey: queryKeys.projectIntegrations(projectId ?? ""),
    queryFn: () => listProjectIntegrations(projectId!),
    enabled: Boolean(projectId),
  });

  if (projectQuery.isLoading || integrationsQuery.isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-48 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (projectQuery.isError || !projectQuery.data) {
    return <ErrorRetryAlert message="Failed to load project." onRetry={() => projectQuery.refetch()} />;
  }

  if (integrationsQuery.isError) {
    return <ErrorRetryAlert message="Failed to load integrations." onRetry={() => integrationsQuery.refetch()} />;
  }

  const project = projectQuery.data;
  const items = integrationsQuery.data?.items ?? [];
  const githubSummary = items.find((item) => item.provider === "github_actions");
  const deferredSummaries = items.filter((item) => item.provider !== "github_actions");

  return (
    <div>
      <PageHeader
        title="Integrations"
        description="Connect CI/CD and infrastructure providers to automatically detect and diagnose failures."
        breadcrumbs={
          <Breadcrumbs
            items={[
              { label: "Projects", to: "/projects" },
              { label: project.name, to: `/projects/${project.id}` },
              { label: "Integrations" },
            ]}
          />
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <GitHubCard projectId={project.id} summary={githubSummary} canManage={canManage} />

        <IntegrationCard
          icon={UploadCloud}
          title="Manual Upload"
          description="Upload CI/CD logs and configuration files directly to create an incident for analysis."
        >
          <Badge tone="success" dot>
            Always available
          </Badge>
          <div>
            <LinkButton to="/incidents/new" variant="outline" size="sm">
              Create incident
            </LinkButton>
          </div>
        </IntegrationCard>

        {deferredSummaries.map((item) => (
          <IntegrationCard
            key={item.provider}
            icon={CloudCog}
            title={item.display_name}
            description="Automated ingestion for this provider is planned for a future release."
          >
            <Badge tone="neutral">Coming later</Badge>
          </IntegrationCard>
        ))}

        {FRONTEND_ONLY_DEFERRED.map((item) => (
          <IntegrationCard
            key={item.provider}
            icon={CloudCog}
            title={item.display_name}
            description="Automated ingestion for this provider is planned for a future release."
          >
            <Badge tone="neutral">Coming later</Badge>
          </IntegrationCard>
        ))}
      </div>
    </div>
  );
}
