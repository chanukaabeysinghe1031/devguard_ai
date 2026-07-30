import { useEffect, useMemo, useRef, useState } from "react";
import { Github, Lock } from "lucide-react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";

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
import { Skeleton } from "../../components/ui/Skeleton";
import { useAuth } from "../../hooks/useAuth";
import type { GitHubInstallationResponse, GitHubRepositoryResponse } from "../../types/integration";

const ADMIN_ROLES = ["organization_owner", "organization_admin"] as const;

function describeError(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
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

  const completeSetupMutation = useMutation({
    mutationFn: () =>
      completeGithubSetup({
        installation_id: Number(installationIdParam),
        state: stateParam ?? "",
      }),
  });

  const setupTriggered = useRef(false);
  useEffect(() => {
    if (canManage && hasSetupParams && !setupTriggered.current) {
      setupTriggered.current = true;
      completeSetupMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canManage, hasSetupParams]);

  const installationsQuery = useQuery({
    queryKey: queryKeys.githubInstallations(),
    queryFn: listGithubInstallations,
    enabled: canManage && !hasSetupParams,
  });

  const resolvedInstallation = hasSetupParams ? completeSetupMutation.data?.installation ?? null : devInstallation;
  const resolvedProjectId = hasSetupParams ? completeSetupMutation.data?.project_id ?? null : projectIdParam;

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
        description="Finish connecting your GitHub App installation to a DevGuard AI project."
      />

      {hasSetupParams ? (
        completeSetupMutation.isPending || completeSetupMutation.isIdle ? (
          <Skeleton className="h-40 w-full" />
        ) : completeSetupMutation.isError ? (
          <ErrorRetryAlert
            message={describeError(completeSetupMutation.error)}
            onRetry={() => completeSetupMutation.mutate()}
          />
        ) : null
      ) : (
        <Card className="mb-6">
          <CardHeader title="Development mode" subtitle="No GitHub redirect parameters were found." />
          <CardBody className="flex flex-col gap-4">
            {!projectIdParam && (
              <Alert variant="warning" title="Missing project context">
                Add a <code>project_id</code> query parameter, or start this flow from a project&apos;s integrations
                page.
              </Alert>
            )}
            {installationsQuery.isLoading ? (
              <Skeleton className="h-11 w-full" />
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
      )}

      {resolvedInstallation && (
        <Card>
          <CardHeader
            title="Choose a repository"
            subtitle={`Installation: ${resolvedInstallation.github_account_login}`}
          />
          <CardBody>
            {!resolvedProjectId ? (
              <Alert variant="danger">Missing project context; return to the project integrations page.</Alert>
            ) : repositoriesQuery.isLoading ? (
              <Skeleton className="h-48 w-full" />
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
                      Connect
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
