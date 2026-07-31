import type { Dispatch, SetStateAction } from "react";
import { useEffect, useState } from "react";
import { CheckCircle2, Github, Pause, Play, PlugZap, RefreshCcw, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import {
  createGithubInstallUrl,
  disconnectProjectGithub,
  getGithubStatus,
  getProjectGithubConnection,
  listGithubInstallations,
  listProjectGithubActivity,
  pauseProjectGithub,
  resumeProjectGithub,
  testProjectGithub,
  updateProjectGithub,
} from "../../api/integrationsApi";
import { getProject } from "../../api/projectsApi";
import { queryKeys } from "../../api/queryKeys";
import { Alert, ErrorRetryAlert } from "../../components/ui/Alert";
import { Badge } from "../../components/ui/Badge";
import { Breadcrumbs } from "../../components/ui/Breadcrumbs";
import { Button } from "../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { EmptyState } from "../../components/ui/EmptyState";
import { KeyValueList } from "../../components/ui/KeyValueList";
import { PageHeader } from "../../components/ui/PageHeader";
import { Select } from "../../components/ui/Select";
import { Skeleton, SkeletonText } from "../../components/ui/Skeleton";
import { Textarea } from "../../components/ui/Textarea";
import { useAuth } from "../../hooks/useAuth";
import type {
  BranchFilterMode,
  ConnectionResponse,
  ConnectionTestResponse,
  WebhookActivityItem,
  WorkflowFilterMode,
} from "../../types/integration";
import { cn } from "../../utils/cn";
import { formatDateTime, formatRelativeTime, titleCase } from "../../utils/formatters";
import { isSafeGitHubUrl } from "../../utils/githubUrl";
import type { BadgeTone } from "../../utils/statusMaps";

const ADMIN_ROLES = ["organization_owner", "organization_admin"] as const;

const FAILURE_CONCLUSION_OPTIONS = ["failure", "timed_out", "action_required", "startup_failure"];

const SEVERITY_OPTIONS = [
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

const ACTIVITY_STATUS_TONE: Record<string, BadgeTone> = {
  completed: "success",
  ignored: "neutral",
  failed: "danger",
  retrying: "warning",
};

interface FormState {
  auto_create_incidents: boolean;
  auto_start_analysis: boolean;
  notify_on_failure: boolean;
  workflowMode: WorkflowFilterMode;
  workflowNames: string;
  branchMode: BranchFilterMode;
  branchPatterns: string;
  failureConclusions: string[];
  severityProduction: string;
  severityStaging: string;
  severityDefault: string;
}

function toFormState(connection: ConnectionResponse): FormState {
  return {
    auto_create_incidents: connection.auto_create_incidents,
    auto_start_analysis: connection.auto_start_analysis,
    notify_on_failure: connection.notify_on_failure,
    workflowMode: connection.workflow_filters.mode,
    workflowNames: connection.workflow_filters.names.join(", "),
    branchMode: connection.branch_filters.mode,
    branchPatterns: connection.branch_filters.patterns.join(", "),
    failureConclusions: connection.failure_conclusions,
    severityProduction: connection.severity_rules.production ?? "critical",
    severityStaging: connection.severity_rules.staging ?? "high",
    severityDefault: connection.severity_rules.default ?? "medium",
  };
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function describeError(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

export function GitHubIntegrationPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasAnyRole } = useAuth();
  const canManage = hasAnyRole([...ADMIN_ROLES]);

  const [form, setForm] = useState<FormState | null>(null);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);

  const projectQuery = useQuery({
    queryKey: queryKeys.project(projectId ?? ""),
    queryFn: () => getProject(projectId!),
    enabled: Boolean(projectId),
  });

  const statusQuery = useQuery({
    queryKey: queryKeys.githubStatus(),
    queryFn: getGithubStatus,
  });

  const connectionQuery = useQuery({
    queryKey: queryKeys.projectGithubConnection(projectId ?? ""),
    queryFn: () => getProjectGithubConnection(projectId!),
    enabled: Boolean(projectId),
    retry: false,
  });

  const isNotConnected =
    connectionQuery.isError && connectionQuery.error instanceof ApiError && connectionQuery.error.status === 404;

  const installationsQuery = useQuery({
    queryKey: queryKeys.githubInstallations(),
    queryFn: listGithubInstallations,
    enabled: Boolean(connectionQuery.data),
  });

  const activityQuery = useQuery({
    queryKey: queryKeys.projectGithubActivity(projectId ?? "", { limit: 30 }),
    queryFn: () => listProjectGithubActivity(projectId!, { limit: 30 }),
    enabled: Boolean(connectionQuery.data),
  });

  useEffect(() => {
    if (connectionQuery.data) {
      setForm(toFormState(connectionQuery.data));
    }
  }, [connectionQuery.data]);

  const installMutation = useMutation({
    mutationFn: () => createGithubInstallUrl({ project_id: projectId! }),
    onSuccess: (data) => {
      window.location.href = data.install_url;
    },
  });

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!form) throw new Error("Form not ready");
      return updateProjectGithub(projectId!, {
        auto_create_incidents: form.auto_create_incidents,
        auto_start_analysis: form.auto_start_analysis,
        notify_on_failure: form.notify_on_failure,
        workflow_filters: { mode: form.workflowMode, names: splitList(form.workflowNames) },
        branch_filters: { mode: form.branchMode, patterns: splitList(form.branchPatterns) },
        failure_conclusions: form.failureConclusions,
        severity_rules: {
          production: form.severityProduction,
          staging: form.severityStaging,
          default: form.severityDefault,
        },
      });
    },
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.projectGithubConnection(projectId ?? ""), data);
      queryClient.invalidateQueries({ queryKey: queryKeys.projectIntegrations(projectId ?? "") });
    },
  });

  const testMutation = useMutation({
    mutationFn: () => testProjectGithub(projectId!),
  });

  const pauseMutation = useMutation({
    mutationFn: () =>
      connectionQuery.data?.is_paused ? resumeProjectGithub(projectId!) : pauseProjectGithub(projectId!),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.projectGithubConnection(projectId ?? ""), data);
      queryClient.invalidateQueries({ queryKey: queryKeys.projectIntegrations(projectId ?? "") });
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: () => disconnectProjectGithub(projectId!),
    onSuccess: () => {
      setConfirmDisconnect(false);
      queryClient.invalidateQueries({ queryKey: queryKeys.projectIntegrations(projectId ?? "") });
      navigate(`/projects/${projectId}/integrations`);
    },
  });

  if (projectQuery.isLoading || connectionQuery.isLoading || statusQuery.isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (projectQuery.isError || !projectQuery.data) {
    return <ErrorRetryAlert message="Failed to load project." onRetry={() => projectQuery.refetch()} />;
  }

  if (connectionQuery.isError && !isNotConnected) {
    return <ErrorRetryAlert message="Failed to load GitHub connection." onRetry={() => connectionQuery.refetch()} />;
  }

  const project = projectQuery.data;
  const connection = connectionQuery.data ?? null;
  const installation =
    connection && installationsQuery.data
      ? installationsQuery.data.items.find((item) => item.github_installation_id === connection.github_installation_id)
      : undefined;

  return (
    <div>
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <Github className="h-6 w-6" /> GitHub Actions
          </span>
        }
        breadcrumbs={
          <Breadcrumbs
            items={[
              { label: "Projects", to: "/projects" },
              { label: project.name, to: `/projects/${project.id}` },
              { label: "Integrations", to: `/projects/${project.id}/integrations` },
              { label: "GitHub" },
            ]}
          />
        }
        description={connection?.repository_full_name ?? "Connect a repository to enable automated failure detection."}
      />

      {!connection ? (
        <EmptyStatePanel
          canManage={canManage}
          appConfigured={Boolean(statusQuery.data?.app_configured && statusQuery.data?.enabled)}
          isFakeProvider={statusQuery.data?.provider === "fake"}
          projectId={project.id}
          isInstalling={installMutation.isPending}
          installError={installMutation.isError ? describeError(installMutation.error) : null}
          onInstall={() => installMutation.mutate()}
        />
      ) : (
        <ConnectedPanel
          connection={connection}
          installationLogin={installation?.github_account_login ?? null}
          canManage={canManage}
          form={form}
          setForm={setForm}
          onSave={() => saveMutation.mutate()}
          isSaving={saveMutation.isPending}
          saveError={saveMutation.isError ? describeError(saveMutation.error) : null}
          saveSuccess={saveMutation.isSuccess}
          onTest={() => testMutation.mutate()}
          isTesting={testMutation.isPending}
          testResult={testMutation.data ?? null}
          testError={testMutation.isError ? describeError(testMutation.error) : null}
          onTogglePause={() => pauseMutation.mutate()}
          isTogglingPause={pauseMutation.isPending}
          onDisconnect={() => setConfirmDisconnect(true)}
          activity={activityQuery.data?.items ?? []}
          activityLoading={activityQuery.isLoading}
        />
      )}

      <ConfirmDialog
        isOpen={confirmDisconnect}
        title="Disconnect GitHub Actions?"
        description="DevGuard AI will stop receiving workflow events for this repository. Existing incidents are kept."
        confirmLabel="Disconnect"
        isDangerous
        isLoading={disconnectMutation.isPending}
        onConfirm={() => disconnectMutation.mutate()}
        onCancel={() => setConfirmDisconnect(false)}
      />
    </div>
  );
}

function EmptyStatePanel({
  canManage,
  appConfigured,
  isFakeProvider,
  projectId,
  isInstalling,
  installError,
  onInstall,
}: {
  canManage: boolean;
  appConfigured: boolean;
  isFakeProvider: boolean;
  projectId: string;
  isInstalling: boolean;
  installError: string | null;
  onInstall: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <EmptyState
        icon={Github}
        title="Connect the DevGuard AI GitHub App"
        description="Install the GitHub App, then choose which repository to connect for automated incident detection."
        action={
          canManage ? (
            <Button
              leftIcon={<PlugZap className="h-4 w-4" />}
              onClick={onInstall}
              isLoading={isInstalling}
              disabled={!appConfigured}
            >
              Install DevGuard AI GitHub App
            </Button>
          ) : (
            <p className="text-sm text-text-muted">Ask an organization owner or admin to connect GitHub Actions.</p>
          )
        }
      />

      {installError && <Alert variant="danger">{installError}</Alert>}
      {!appConfigured && (
        <Alert variant="warning" title="GitHub App not configured">
          The GitHub App is not configured for this environment yet. Contact your platform administrator.
        </Alert>
      )}

      {canManage && isFakeProvider && (
        <Alert variant="info" title="Development mode">
          Running against the fake GitHub provider.{" "}
          <Link to={`/integrations/github/setup?project_id=${projectId}`} className="underline">
            Complete setup using an existing installation
          </Link>{" "}
          without the real GitHub OAuth redirect.
        </Alert>
      )}

      <Card>
        <CardHeader title="Permissions requested" />
        <CardBody>
          <ul className="flex flex-col gap-2 text-sm text-text-secondary">
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-success" /> Metadata: Read-only
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-success" /> Actions: Read-only (workflow run status and logs)
            </li>
          </ul>
          <p className="mt-3 text-sm text-text-muted">
            DevGuard AI never requests write access to your repository and never modifies code, branches, or
            workflows. No self-healing or automatic remediation actions are performed — findings are diagnostic only.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}

interface ConnectedPanelProps {
  connection: ConnectionResponse;
  installationLogin: string | null;
  canManage: boolean;
  form: FormState | null;
  setForm: Dispatch<SetStateAction<FormState | null>>;
  onSave: () => void;
  isSaving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onTest: () => void;
  isTesting: boolean;
  testResult: ConnectionTestResponse | null;
  testError: string | null;
  onTogglePause: () => void;
  isTogglingPause: boolean;
  onDisconnect: () => void;
  activity: WebhookActivityItem[];
  activityLoading: boolean;
}

function ConnectedPanel({
  connection,
  installationLogin,
  canManage,
  form,
  setForm,
  onSave,
  isSaving,
  saveError,
  saveSuccess,
  onTest,
  isTesting,
  testResult,
  testError,
  onTogglePause,
  isTogglingPause,
  onDisconnect,
  activity,
  activityLoading,
}: ConnectedPanelProps) {
  if (!form) {
    return <Skeleton className="h-96 w-full" />;
  }

  const repositoryLinkSafe = isSafeGitHubUrl(connection.repository_url);

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader
          title="Connection"
          subtitle={`Connected ${formatDateTime(connection.created_at)}`}
          action={
            <div className="flex items-center gap-2">
              <Badge tone={connection.is_paused ? "warning" : "success"} dot>
                {connection.is_paused ? "Paused" : "Connected"}
              </Badge>
              {connection.last_error && <Badge tone="danger">Error</Badge>}
            </div>
          }
        />
        <CardBody className="flex flex-col gap-4">
          <KeyValueList
            columns={2}
            items={[
              { label: "Account", value: installationLogin ?? "—" },
              {
                label: "Repository",
                value:
                  repositoryLinkSafe && connection.repository_url ? (
                    <a
                      href={connection.repository_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-primary hover:underline"
                    >
                      {connection.repository_full_name}
                    </a>
                  ) : (
                    connection.repository_full_name
                  ),
              },
              { label: "Default branch", value: connection.default_branch ?? "—" },
              { label: "Last webhook received", value: formatRelativeTime(connection.last_webhook_at) },
              { label: "Last successful sync", value: formatRelativeTime(connection.last_successful_sync_at) },
              { label: "Last error", value: connection.last_error ?? "—" },
            ]}
          />

          {testError && <Alert variant="danger">{testError}</Alert>}
          {testResult && (
            <Alert
              variant={testResult.ok ? "success" : "warning"}
              title={testResult.ok ? "Connection healthy" : "Connection issue"}
            >
              {testResult.message}
            </Alert>
          )}

          {canManage && (
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" leftIcon={<RefreshCcw className="h-4 w-4" />} onClick={onTest} isLoading={isTesting}>
                Test connection
              </Button>
              <Button
                variant="outline"
                leftIcon={connection.is_paused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
                onClick={onTogglePause}
                isLoading={isTogglingPause}
              >
                {connection.is_paused ? "Resume" : "Pause"}
              </Button>
              <Button variant="danger" leftIcon={<Trash2 className="h-4 w-4" />} onClick={onDisconnect}>
                Disconnect
              </Button>
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Automation" subtitle="Control what happens when a workflow run fails." />
        <CardBody className="flex flex-col gap-5">
          {saveError && <Alert variant="danger">{saveError}</Alert>}
          {saveSuccess && <Alert variant="success">Settings saved.</Alert>}

          <div className="flex flex-col gap-3">
            <CheckboxRow
              label="Automatically create incidents"
              checked={form.auto_create_incidents}
              disabled={!canManage}
              onChange={(checked) => setForm((prev) => (prev ? { ...prev, auto_create_incidents: checked } : prev))}
            />
            <CheckboxRow
              label="Automatically start AI analysis"
              checked={form.auto_start_analysis}
              disabled={!canManage}
              onChange={(checked) => setForm((prev) => (prev ? { ...prev, auto_start_analysis: checked } : prev))}
            />
            <CheckboxRow
              label="Notify on failure"
              checked={form.notify_on_failure}
              disabled={!canManage}
              onChange={(checked) => setForm((prev) => (prev ? { ...prev, notify_on_failure: checked } : prev))}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Select
              label="Workflow filter"
              value={form.workflowMode}
              disabled={!canManage}
              onChange={(event) =>
                setForm((prev) => (prev ? { ...prev, workflowMode: event.target.value as WorkflowFilterMode } : prev))
              }
              options={[
                { value: "all", label: "All workflows" },
                { value: "selected", label: "Selected workflows only" },
              ]}
            />
            <Select
              label="Branch filter"
              value={form.branchMode}
              disabled={!canManage}
              onChange={(event) =>
                setForm((prev) => (prev ? { ...prev, branchMode: event.target.value as BranchFilterMode } : prev))
              }
              options={[
                { value: "all", label: "All branches" },
                { value: "default", label: "Default branch only" },
                { value: "patterns", label: "Matching patterns" },
              ]}
            />
          </div>

          {form.workflowMode === "selected" && (
            <Textarea
              label="Workflow names"
              hint="Comma-separated exact workflow names (e.g. CI, Deploy)."
              rows={2}
              value={form.workflowNames}
              disabled={!canManage}
              onChange={(event) => setForm((prev) => (prev ? { ...prev, workflowNames: event.target.value } : prev))}
            />
          )}

          {form.branchMode === "patterns" && (
            <Textarea
              label="Branch patterns"
              hint="Comma-separated glob patterns (e.g. main, release/*)."
              rows={2}
              value={form.branchPatterns}
              disabled={!canManage}
              onChange={(event) => setForm((prev) => (prev ? { ...prev, branchPatterns: event.target.value } : prev))}
            />
          )}

          <div>
            <p className="mb-2 text-sm font-medium text-text-secondary">Failure conclusions</p>
            <div className="flex flex-wrap gap-4">
              {FAILURE_CONCLUSION_OPTIONS.map((option) => (
                <CheckboxRow
                  key={option}
                  label={titleCase(option)}
                  checked={form.failureConclusions.includes(option)}
                  disabled={!canManage}
                  onChange={(checked) =>
                    setForm((prev) =>
                      prev
                        ? {
                            ...prev,
                            failureConclusions: checked
                              ? [...prev.failureConclusions, option]
                              : prev.failureConclusions.filter((item) => item !== option),
                          }
                        : prev,
                    )
                  }
                />
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Select
              label="Production severity"
              value={form.severityProduction}
              disabled={!canManage}
              onChange={(event) =>
                setForm((prev) => (prev ? { ...prev, severityProduction: event.target.value } : prev))
              }
              options={SEVERITY_OPTIONS}
            />
            <Select
              label="Staging severity"
              value={form.severityStaging}
              disabled={!canManage}
              onChange={(event) => setForm((prev) => (prev ? { ...prev, severityStaging: event.target.value } : prev))}
              options={SEVERITY_OPTIONS}
            />
            <Select
              label="Default severity"
              value={form.severityDefault}
              disabled={!canManage}
              onChange={(event) => setForm((prev) => (prev ? { ...prev, severityDefault: event.target.value } : prev))}
              options={SEVERITY_OPTIONS}
            />
          </div>

          {canManage && (
            <div className="flex justify-end">
              <Button onClick={onSave} isLoading={isSaving}>
                Save changes
              </Button>
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Recent activity" subtitle="Latest inbound GitHub webhook deliveries for this repository." />
        <CardBody className="!p-0">
          <ActivityList activity={activity} isLoading={activityLoading} />
        </CardBody>
      </Card>
    </div>
  );
}

function CheckboxRow({
  label,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className={cn("flex items-center gap-2 text-sm text-text-secondary", disabled && "opacity-60")}>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 rounded border-border-strong bg-surface-interactive text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
      />
      {label}
    </label>
  );
}

function ActivityList({ activity, isLoading }: { activity: WebhookActivityItem[]; isLoading: boolean }) {
  if (isLoading) {
    return (
      <div className="p-5">
        <SkeletonText lines={4} />
      </div>
    );
  }

  if (activity.length === 0) {
    return (
      <div className="p-5">
        <EmptyState title="No activity yet" description="Webhook deliveries for this repository will appear here." />
      </div>
    );
  }

  return (
    <ul className="divide-y divide-border">
      {activity.map((item) => (
        <li key={item.id} className="flex flex-col gap-1 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-text-primary">
              {item.event_name}
              {item.event_action ? `.${item.event_action}` : ""}
              {item.workflow_name ? ` · ${item.workflow_name}` : ""}
            </p>
            <p className="text-xs text-text-muted">
              {item.branch ?? "—"}
              {item.conclusion ? ` · ${item.conclusion}` : ""} · {formatRelativeTime(item.received_at)}
            </p>
            {item.error_message && <p className="text-xs text-danger">{item.error_message}</p>}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Badge tone={ACTIVITY_STATUS_TONE[item.processing_status] ?? "info"}>
              {titleCase(item.processing_status)}
            </Badge>
            {item.related_incident_id && (
              <Link to={`/incidents/${item.related_incident_id}`} className="text-xs text-primary hover:underline">
                View incident
              </Link>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
