import { useMemo } from "react";
import { AlertTriangle, Cpu, FolderKanban, Rocket, ShieldCheck, TrendingUp } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";

import * as dashboardApi from "../../api/dashboardApi";
import { listProjects } from "../../api/projectsApi";
import { queryKeys } from "../../api/queryKeys";
import { Button } from "../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorRetryAlert } from "../../components/ui/Alert";
import { LinkButton } from "../../components/ui/LinkButton";
import { MetricCard } from "../../components/ui/MetricCard";
import { PageHeader } from "../../components/ui/PageHeader";
import { SeverityBadge } from "../../components/ui/SeverityBadge";
import { Skeleton, SkeletonCard } from "../../components/ui/Skeleton";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { formatDurationMs, formatNumber, formatRelativeTime } from "../../utils/formatters";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "var(--danger)",
  high: "var(--warning)",
  medium: "var(--info)",
  low: "var(--text-muted)",
};

export function DashboardPage() {
  const projectsQuery = useQuery({
    queryKey: queryKeys.projects({ page: 1, page_size: 1 }),
    queryFn: () => listProjects({ page: 1, page_size: 1 }),
  });

  const summaryQuery = useQuery({
    queryKey: queryKeys.dashboardSummary(),
    queryFn: () => dashboardApi.getDashboardSummary(),
  });

  const trendQuery = useQuery({
    queryKey: queryKeys.dashboardTrend({ interval: "day" }),
    queryFn: () => dashboardApi.getIncidentTrend({ interval: "day" }),
  });

  const severityQuery = useQuery({
    queryKey: queryKeys.dashboardSeverity(),
    queryFn: () => dashboardApi.getSeverityDistribution(),
  });

  const failureCategoriesQuery = useQuery({
    queryKey: queryKeys.dashboardFailureCategories(),
    queryFn: () => dashboardApi.getFailureCategories(),
  });

  const recentIncidentsQuery = useQuery({
    queryKey: queryKeys.dashboardRecentIncidents({ limit: 6 }),
    queryFn: () => dashboardApi.getRecentIncidents({ limit: 6 }),
  });

  const activeAnalysesQuery = useQuery({
    queryKey: queryKeys.dashboardActiveAnalyses({ limit: 6 }),
    queryFn: () => dashboardApi.getActiveAnalyses({ limit: 6 }),
  });

  const activityQuery = useQuery({
    queryKey: queryKeys.dashboardActivity({ limit: 8 }),
    queryFn: () => dashboardApi.getDashboardActivity({ limit: 8 }),
  });

  const severityChartData = useMemo(() => {
    const dist = severityQuery.data;
    if (!dist) return [];
    return (["critical", "high", "medium", "low"] as const)
      .map((key) => ({ name: key, value: dist[key] }))
      .filter((item) => item.value > 0);
  }, [severityQuery.data]);

  const hasNoProjects = projectsQuery.data?.total_items === 0;

  if (projectsQuery.isLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Skeleton className="h-10 w-10 rounded-full" />
      </div>
    );
  }

  if (hasNoProjects) {
    return (
      <div>
        <PageHeader title="Dashboard" description="An overview of incidents, deployments, and AI analyses." />
        <EmptyState
          title="Create your first project to get started"
          description="Connect a project to start tracking pipeline runs and diagnosing CI/CD incidents with AI."
          action={<LinkButton to="/projects/new">Create project</LinkButton>}
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="An overview of incidents, deployments, and AI analyses across your organization."
        actions={
          <Link to="/incidents/new">
            <Button>New incident</Button>
          </Link>
        }
      />

      {summaryQuery.isError ? (
        <ErrorRetryAlert message="Failed to load dashboard metrics." onRetry={() => summaryQuery.refetch()} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Open incidents"
            value={formatNumber(summaryQuery.data?.open_incidents)}
            icon={AlertTriangle}
            tone="warning"
            isLoading={summaryQuery.isLoading}
          />
          <MetricCard
            label="Critical incidents"
            value={formatNumber(summaryQuery.data?.critical_incidents)}
            icon={ShieldCheck}
            tone="danger"
            isLoading={summaryQuery.isLoading}
          />
          <MetricCard
            label="Active analyses"
            value={formatNumber(summaryQuery.data?.active_analyses)}
            icon={Cpu}
            tone="info"
            isLoading={summaryQuery.isLoading}
          />
          <MetricCard
            label="Resolved today"
            value={formatNumber(summaryQuery.data?.resolved_today)}
            icon={TrendingUp}
            tone="success"
            isLoading={summaryQuery.isLoading}
          />
        </div>
      )}

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Deployment success rate"
          value={
            summaryQuery.data?.deployment_success_rate == null
              ? "—"
              : `${summaryQuery.data.deployment_success_rate.toFixed(0)}%`
          }
          icon={Rocket}
          tone="primary"
          isLoading={summaryQuery.isLoading}
        />
        <MetricCard
          label="Failed deployments"
          value={formatNumber(summaryQuery.data?.failed_deployments)}
          icon={AlertTriangle}
          tone="danger"
          isLoading={summaryQuery.isLoading}
        />
        <MetricCard
          label="Successful deployments"
          value={formatNumber(summaryQuery.data?.successful_deployments)}
          icon={ShieldCheck}
          tone="success"
          isLoading={summaryQuery.isLoading}
        />
        <MetricCard
          label="Avg. resolution time"
          value={
            summaryQuery.data?.average_resolution_minutes != null
              ? formatDurationMs(summaryQuery.data.average_resolution_minutes * 60_000)
              : "—"
          }
          icon={FolderKanban}
          tone="secondary"
          isLoading={summaryQuery.isLoading}
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Incident trend" subtitle="Detected vs. resolved incidents over time" />
          <CardBody>
            {trendQuery.isLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : !trendQuery.data?.items.length ? (
              <EmptyState title="No trend data yet" description="Incident trends will appear once incidents are detected." />
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={trendQuery.data.items}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="period" stroke="var(--text-muted)" fontSize={12} />
                  <YAxis stroke="var(--text-muted)" fontSize={12} allowDecimals={false} />
                  <RechartsTooltip
                    contentStyle={{
                      background: "var(--surface-elevated)",
                      border: "1px solid var(--border-strong)",
                      borderRadius: 8,
                      color: "var(--text-primary)",
                    }}
                  />
                  <Line type="monotone" dataKey="incident_count" name="Detected" stroke="var(--primary)" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="resolved_count" name="Resolved" stroke="var(--success)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Severity distribution" />
          <CardBody>
            {severityQuery.isLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : severityChartData.length === 0 ? (
              <EmptyState title="No incidents yet" description="Severity breakdown appears once incidents exist." />
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={severityChartData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
                    {severityChartData.map((entry) => (
                      <Cell key={entry.name} fill={SEVERITY_COLORS[entry.name] ?? "var(--text-muted)"} />
                    ))}
                  </Pie>
                  <RechartsTooltip
                    contentStyle={{
                      background: "var(--surface-elevated)",
                      border: "1px solid var(--border-strong)",
                      borderRadius: 8,
                      color: "var(--text-primary)",
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Top failure categories" />
          <CardBody>
            {failureCategoriesQuery.isLoading ? (
              <Skeleton className="h-56 w-full" />
            ) : !failureCategoriesQuery.data?.items.length ? (
              <EmptyState title="No classifications yet" description="Failure categories appear after analyses complete." />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={failureCategoriesQuery.data.items} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis type="number" stroke="var(--text-muted)" fontSize={12} allowDecimals={false} />
                  <YAxis type="category" dataKey="category" stroke="var(--text-muted)" fontSize={12} width={110} />
                  <RechartsTooltip
                    contentStyle={{
                      background: "var(--surface-elevated)",
                      border: "1px solid var(--border-strong)",
                      borderRadius: 8,
                      color: "var(--text-primary)",
                    }}
                  />
                  <Bar dataKey="count" fill="var(--primary)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Recent incidents" action={<Link to="/incidents" className="text-sm text-primary hover:underline">View all</Link>} />
          <CardBody className="!p-0">
            {recentIncidentsQuery.isLoading ? (
              <div className="p-5">
                <SkeletonCard />
              </div>
            ) : !recentIncidentsQuery.data?.items.length ? (
              <div className="p-5">
                <EmptyState title="No recent incidents" description="New incidents will show up here." />
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {recentIncidentsQuery.data.items.map((incident) => (
                  <li key={incident.id}>
                    <Link
                      to={`/incidents/${incident.id}`}
                      className="flex flex-col gap-1.5 px-5 py-3 transition-colors hover:bg-surface-hover"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-medium text-text-primary">{incident.title}</span>
                        <SeverityBadge severity={incident.severity} />
                      </div>
                      <div className="flex items-center justify-between text-xs text-text-muted">
                        <span>{incident.project.name}</span>
                        <span>{formatRelativeTime(incident.detected_at)}</span>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Active analyses" />
          <CardBody className="!p-0">
            {activeAnalysesQuery.isLoading ? (
              <div className="p-5">
                <SkeletonCard />
              </div>
            ) : !activeAnalysesQuery.data?.items.length ? (
              <div className="p-5">
                <EmptyState title="No active analyses" description="AI analyses in progress will appear here." />
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {activeAnalysesQuery.data.items.map((analysis) => (
                  <li key={analysis.id}>
                    <Link
                      to={`/incidents/${analysis.incident_id}/analysis`}
                      className="flex flex-col gap-1.5 px-5 py-3 transition-colors hover:bg-surface-hover"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-medium text-text-primary">
                          {analysis.incident_title}
                        </span>
                        <StatusBadge kind="analysis" status={analysis.status} />
                      </div>
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-interactive">
                        <div
                          className="h-full rounded-full bg-primary transition-all"
                          style={{ width: `${analysis.progress_percentage}%` }}
                        />
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader title="Recent activity" />
        <CardBody className="!p-0">
          {activityQuery.isLoading ? (
            <div className="p-5">
              <SkeletonCard />
            </div>
          ) : !activityQuery.data?.items.length ? (
            <div className="p-5">
              <EmptyState title="No activity yet" description="Incident events and system activity will show up here." />
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {activityQuery.data.items.map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-3 px-5 py-3">
                  <div>
                    <Link to={`/incidents/${item.incident_id}`} className="text-sm font-medium text-text-primary hover:underline">
                      {item.title}
                    </Link>
                    {item.description && <p className="mt-0.5 text-xs text-text-muted">{item.description}</p>}
                  </div>
                  <span className="shrink-0 text-xs text-text-disabled">{formatRelativeTime(item.occurred_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
