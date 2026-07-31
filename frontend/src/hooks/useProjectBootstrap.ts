import { useQueries } from "@tanstack/react-query";

import { listIncidents } from "../api/incidentsApi";
import { listProjectIntegrations } from "../api/integrationsApi";
import { getProject } from "../api/projectsApi";
import { queryKeys } from "../api/queryKeys";
import type { LoaderStep } from "../components/loading";
import { useMinDisplayTime } from "./useMinDisplayTime";

export interface ProjectBootstrapResult {
  isBootstrapping: boolean;
  isReady: boolean;
  isError: boolean;
  errorMessage: string | null;
  projectName?: string;
  steps: LoaderStep[];
  progress: number;
  retry: () => void;
}

function stepStatus(opts: {
  isError: boolean;
  hasData: boolean;
  isPending: boolean;
  softFail?: boolean;
}): LoaderStep["status"] {
  if (opts.isError) return opts.softFail ? "done" : "error";
  if (opts.hasData) return "done";
  if (opts.isPending) return "active";
  return "pending";
}

/**
 * Loads essential project context once when entering a project route.
 * Full-screen bootstrap only when project detail is not yet cached.
 */
export function useProjectBootstrap(projectId: string | undefined): ProjectBootstrapResult {
  const enabled = Boolean(projectId);

  const results = useQueries({
    queries: [
      {
        queryKey: queryKeys.project(projectId ?? ""),
        queryFn: () => getProject(projectId!),
        enabled,
        staleTime: 30_000,
      },
      {
        queryKey: queryKeys.incidents({ project_id: projectId, page: 1, page_size: 20 }),
        queryFn: () => listIncidents({ project_id: projectId, page: 1, page_size: 20 }),
        enabled,
        staleTime: 15_000,
      },
      {
        queryKey: queryKeys.projectIntegrations(projectId ?? ""),
        queryFn: () => listProjectIntegrations(projectId!),
        enabled,
        staleTime: 30_000,
        retry: false,
      },
    ],
  });

  const projectQuery = results[0];
  const incidentsQuery = results[1];
  const integrationsQuery = results[2];

  const coldStart =
    enabled && !projectQuery.data && (projectQuery.isPending || projectQuery.fetchStatus === "fetching");
  const waitingIncidents =
    coldStart ||
    (enabled && !incidentsQuery.data && incidentsQuery.isPending && !projectQuery.isError);
  const needsBootstrap = coldStart || waitingIncidents;
  const minElapsed = useMinDisplayTime(needsBootstrap && !projectQuery.isError, 650);

  const isError = projectQuery.isError || incidentsQuery.isError;
  const errorMessage = isError
    ? (projectQuery.error instanceof Error && projectQuery.error.message) ||
      (incidentsQuery.error instanceof Error && incidentsQuery.error.message) ||
      "Failed to load project."
    : null;

  const detail = stepStatus({
    isError: projectQuery.isError,
    hasData: Boolean(projectQuery.data),
    isPending: projectQuery.isPending || projectQuery.fetchStatus === "fetching",
  });
  const incidents = stepStatus({
    isError: incidentsQuery.isError,
    hasData: Boolean(incidentsQuery.data),
    isPending: incidentsQuery.isPending || incidentsQuery.fetchStatus === "fetching",
  });
  const integrations = stepStatus({
    isError: integrationsQuery.isError,
    hasData: Boolean(integrationsQuery.data),
    isPending: integrationsQuery.isPending || integrationsQuery.fetchStatus === "fetching",
    softFail: true,
  });

  const steps: LoaderStep[] = [
    { id: "details", label: "Loading project details", status: detail },
    { id: "access", label: "Checking your access", status: detail },
    { id: "incidents", label: "Fetching incident overview", status: incidents },
    { id: "integrations", label: "Loading GitHub integration status", status: integrations },
    {
      id: "ai",
      label: "Preparing AI analysis context",
      status:
        projectQuery.data && incidentsQuery.data
          ? "done"
          : projectQuery.data
            ? "active"
            : "pending",
    },
  ];

  const doneCount = steps.filter((s) => s.status === "done").length;
  const progress = steps.length ? doneCount / steps.length : 0;
  const hardReady = Boolean(projectQuery.data && incidentsQuery.data);
  const isBootstrapping = Boolean(needsBootstrap && !isError && (!hardReady || !minElapsed));

  return {
    isBootstrapping,
    isReady: hardReady && !isBootstrapping && !isError,
    isError,
    errorMessage,
    projectName: projectQuery.data?.name,
    steps,
    progress,
    retry: () => {
      void projectQuery.refetch();
      void incidentsQuery.refetch();
      void integrationsQuery.refetch();
    },
  };
}
