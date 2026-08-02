import { useEffect, useMemo, useState } from "react";
import { Github, Lock } from "lucide-react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import {
  completeGithubSetup,
  connectProjectGithub,
  listGithubInstallations,
  listInstallationRepositories,
} from "../../api/integrationsApi";
import { queryKeys } from "../../api/queryKeys";
import { Alert, ErrorRetryAlert } from "../../components/ui/Alert";
import { Badge } from "../../components/ui/Badge";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { PageHeader } from "../../components/ui/PageHeader";
import { Select } from "../../components/ui/Select";
import { Spinner } from "../../components/ui/Spinner";
import { useAuth } from "../../hooks/useAuth";
import type { GitHubInstallationResponse, GitHubRepositoryResponse, SetupCompleteResponse } from "../../types/integration";

const ADMIN_ROLES = ["organization_owner", "organization_admin"] as const;

function describeError(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

function SetupConnectingPanel({ elapsedSeconds }: { elapsedSeconds: number }) {
  return (
    <Card className="mb-6 overflow-hidden">
      <CardBody className="relative flex flex-col items-center justify-center gap-4 py-14">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(37,99,235,0.12),transparent_65%)]"
        />
        <div className="relative flex h-16 w-16 items-center justify-center rounded-full border border-border-strong bg-surface">
          <span className="absolute inset-0 animate-ping rounded-full bg-primary/20" />
          <Spinner size="lg" className="relative text-primary" />
        </div>
        <div className="relative text-center">
          <p className="text-base font-semibold text-text-primary">Connecting GitHub App installation</p>
          <p className="mt-1 max-w-md text-sm text-text-muted">
            Verifying the installation with GitHub and linking it to your organization. This usually takes a few
            seconds.
          </p>
          <p className="mt-3 font-mono text-xs text-text-muted" aria-live="polite">
            Elapsed {elapsedSeconds}s
            {elapsedSeconds >= 8 ? " — still working, please wait…" : ""}
          </p>
        </div>
      </CardBody>
    </Card>
  );
}

export function GitHubSetupCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { hasAnyRole } = useAuth();
  const canManage = hasAnyRole([...ADMIN_ROLES]);

  const installationIdParam = searchParams.get("installation_id");
  const stateParam = searchParams.get("state");
  const projectIdParam = searchParams.get("project_id");
  const hasSetupParams = Boolean(installationIdParam && stateParam);

  const [devInstallation, setDevInstallation] = useState<GitHubInstallationResponse | null>(null);
  const [setupResult, setSetupResult] = useState<SetupCompleteResponse | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const completeSetupMutation = useMutation({
    mutationFn: () =>
      completeGithubSetup({
        installation_id: Number(installationIdParam),
        state: stateParam ?? "",
      }),
    onSuccess: (data) => {
      setSetupResult(data);
    },
  });

  // Always (re)run setup when callback params are present. Avoid ref+isIdle traps that leave a blank skeleton.
  useEffect(() => {
    if (!canManage || !hasSetupParams) {
      return;
    }
    if (completeSetupMutation.isPending || setupResult) {
      return;
    }
    if (completeSetupMutation.isError) {
      return;
    }
    completeSetupMutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canManage, hasSetupParams, installationIdParam, stateParam]);

  useEffect(() => {
    if (!hasSetupParams || setupResult || completeSetupMutation.isError) {
      setElapsedSeconds(0);
      return;
    }
    setElapsedSeconds(0);
    const timer = window.setInterval(() => {
      setElapsedSeconds((value) => value + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [hasSetupParams, setupResult, completeSetupMutation.isError, completeSetupMutation.isPending]);

  const installationsQuery = useQuery({
    queryKey: queryKeys.githubInstallations(),
    queryFn: listGithubInstallations,
    enabled: canManage && (!hasSetupParams || completeSetupMutation.isError),
  });

  const resolvedInstallation = hasSetupParams
    ? setupResult?.installation ?? null
    : devInstallation;
  const resolvedProjectId = hasSetupParams ? setupResult?.project_id ?? null : projectIdParam;

  const repositoriesQuery = useQuery({
    queryKey: queryKeys.githubInstallationRepositories(resolvedInstallation?.id ?? ""),
    queryFn: () => listInstallationRepositories(resolvedInstallation!.id),
    enabled: Boolean(resolvedInstallation?.id),
  });

  const connectMutation = useMutation({
    mutationFn: (repository: GitHubRepositoryResponse) => {
      if (!resolvedInstallation || !resolvedProjectId) {
        throw new Error("Missing installation or project context");
      }
      return connectProjectGithub(resolvedProjectId, {
        installation_id: resolvedInstallation.id,
        github_repository_id: repository.github_repository_id,
        repository_full_name: repository.full_name,
        repository_url: repository.html_url,
        default_branch: repository.default_branch,
      });
    },
    onSuccess: () => {
      navigate(`/projects/${resolvedProjectId}/integrations`);
    },
  });

  const availableRepositories = useMemo(
    () => (repositoriesQuery.data?.items ?? []).filter((repo) => !repo.connected_project_id),
    [repositoriesQuery.data],
  );

  const isSetupLoading =
    hasSetupParams && !setupResult && !completeSetupMutation.isError && canManage;

  if (!canManage) {
    return (
      <div>
        <PageHeader title="GitHub setup" />
        <Alert variant="danger" title="Insufficient permissions">
          Only organization owners and admins can complete GitHub App setup.
        </Alert>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <Github className="h-6 w-6" /> GitHub setup
          </span>
        }
        description="Link a GitHub App installation to this organization, then map a repository to your project. The same installation can be reused across organizations and projects."
      />

      {isSetupLoading ? (
        <SetupConnectingPanel elapsedSeconds={elapsedSeconds} />
      ) : hasSetupParams && completeSetupMutation.isError ? (
        <div className="mb-6 flex flex-col gap-4">
          <ErrorRetryAlert
            message={describeError(completeSetupMutation.error)}
            onRetry={() => {
              setSetupResult(null);
              completeSetupMutation.reset();
              completeSetupMutation.mutate();
            }}
          />
          <Card>
            <CardHeader
              title="Continue with an existing installation"
              subtitle="If setup already succeeded once, pick the installation below and open your project integrations page."
            />
            <CardBody className="flex flex-col gap-4">
              {installationsQuery.isLoading ? (
                <div className="flex items-center gap-3 text-sm text-text-muted">
                  <Spinner size="sm" /> Loading installations…
                </div>
              ) : installationsQuery.isError ? (
                <ErrorRetryAlert
                  message="Failed to load installations."
                  onRetry={() => installationsQuery.refetch()}
                />
              ) : (installationsQuery.data?.items.length ?? 0) === 0 ? (
                <Alert variant="warning">
                  No installations are registered yet. Retry setup, or install the App again from a project&apos;s
                  Integrations page.
                </Alert>
              ) : (
                <>
                  <Select
                    label="GitHub App installation"
                    placeholder="Select an installation"
                    value={devInstallation?.id ?? ""}
                    onChange={(event) => {
                      const found = installationsQuery.data?.items.find((item) => item.id === event.target.value);
                      setDevInstallation(found ?? null);
                    }}
                    options={(installationsQuery.data?.items ?? []).map((item) => ({
                      value: item.id,
                      label: `${item.github_account_login} (#${item.github_installation_id})`,
                    }))}
                  />
                  <Alert variant="info">
                    Then open{" "}
                    <Link to="/projects" className="underline">
                      Projects
                    </Link>
                    , choose a project → Integrations → GitHub Actions, and use{" "}
                    <strong>Complete setup using an existing installation</strong>.
                  </Alert>
                </>
              )}
            </CardBody>
          </Card>
        </div>
      ) : !hasSetupParams ? (
        <Card className="mb-6">
          <CardHeader title="Manual setup" subtitle="No GitHub redirect parameters were found." />
          <CardBody className="flex flex-col gap-4">
            {!projectIdParam && (
              <Alert variant="warning" title="Missing project context">
                Start from a project&apos;s Integrations page, or add a <code>project_id</code> query parameter.
              </Alert>
            )}
            {installationsQuery.isLoading ? (
              <div className="flex items-center gap-3 text-sm text-text-muted">
                <Spinner size="sm" /> Loading installations…
              </div>
            ) : installationsQuery.isError ? (
              <ErrorRetryAlert message="Failed to load installations." onRetry={() => installationsQuery.refetch()} />
            ) : (
              <Select
                label="GitHub App installation"
                placeholder="Select an installation"
                disabled={!projectIdParam}
                value={devInstallation?.id ?? ""}
                onChange={(event) => {
                  const found = installationsQuery.data?.items.find((item) => item.id === event.target.value);
                  setDevInstallation(found ?? null);
                }}
                options={(installationsQuery.data?.items ?? []).map((item) => ({
                  value: item.id,
                  label: `${item.github_account_login} (#${item.github_installation_id})`,
                }))}
              />
            )}
          </CardBody>
        </Card>
      ) : setupResult ? (
        <Alert variant="success" title="GitHub installation found" className="mb-6">
          GitHub account <strong>{setupResult.installation.github_account_login}</strong> is linked to this
          organization and can be reused across multiple projects. Choose a repository below to map it to your
          project.
        </Alert>
      ) : null}

      {resolvedInstallation && (
        <Card>
          <CardHeader
            title="Choose a repository"
            subtitle={`Installation: ${resolvedInstallation.github_account_login}`}
          />
          <CardBody>
            {!resolvedProjectId ? (
              <Alert variant="danger" title="Missing project context">
                The install link did not include a project. Go to{" "}
                <Link to="/projects" className="underline">
                  Projects
                </Link>{" "}
                → your project → Integrations → GitHub Actions →{" "}
                <strong>Complete setup using an existing installation</strong>.
              </Alert>
            ) : repositoriesQuery.isLoading ? (
              <div className="flex flex-col items-center gap-3 py-10">
                <Spinner size="lg" className="text-primary" />
                <p className="text-sm text-text-muted">Loading repositories from GitHub…</p>
              </div>
            ) : repositoriesQuery.isError ? (
              <ErrorRetryAlert message="Failed to load repositories." onRetry={() => repositoriesQuery.refetch()} />
            ) : availableRepositories.length === 0 ? (
              <Alert variant="info">
                No unconnected repositories are available for this installation. Grant repository access from
                GitHub, or choose a different installation.
              </Alert>
            ) : (
              <ul className="flex flex-col gap-2">
                {availableRepositories.map((repo) => (
                  <li
                    key={repo.github_repository_id}
                    className="flex items-center justify-between gap-3 rounded-md border border-border-strong px-4 py-3"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-text-primary">{repo.full_name}</span>
                      {repo.private && (
                        <Badge tone="neutral">
                          <Lock className="h-3 w-3" /> Private
                        </Badge>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => connectMutation.mutate(repo)}
                      disabled={connectMutation.isPending}
                      className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {connectMutation.isPending ? (
                        <span className="inline-flex items-center gap-2">
                          <Spinner size="sm" /> Connecting…
                        </span>
                      ) : (
                        "Connect"
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {connectMutation.isError && (
              <div className="mt-4">
                <Alert variant="danger">{describeError(connectMutation.error)}</Alert>
              </div>
            )}
          </CardBody>
        </Card>
      )}
    </div>
  );
}
