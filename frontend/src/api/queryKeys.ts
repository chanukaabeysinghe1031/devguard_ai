/** Central TanStack Query key factory to keep cache invalidation consistent. */
export const queryKeys = {
  me: () => ["me"] as const,
  organization: () => ["organization", "current"] as const,
  organizationMembers: (orgId: string) => ["organization", orgId, "members"] as const,

  projects: (params?: Record<string, unknown>) => ["projects", params ?? {}] as const,
  project: (id: string) => ["projects", id] as const,

  pipelineRuns: (projectId: string, params?: Record<string, unknown>) =>
    ["pipeline-runs", projectId, params ?? {}] as const,
  pipelineRun: (id: string) => ["pipeline-runs", "detail", id] as const,

  incidents: (params?: Record<string, unknown>) => ["incidents", params ?? {}] as const,
  incident: (id: string) => ["incidents", id] as const,
  incidentTimeline: (id: string) => ["incidents", id, "timeline"] as const,
  incidentNotes: (id: string) => ["incidents", id, "notes"] as const,
  incidentFiles: (id: string) => ["incidents", id, "files"] as const,
  incidentAnalyses: (id: string) => ["incidents", id, "analyses"] as const,
  incidentResolutions: (id: string) => ["incidents", id, "resolutions"] as const,

  analysis: (id: string) => ["analyses", id] as const,
  analysisStatus: (id: string) => ["analyses", id, "status"] as const,
  analysisEvidence: (id: string) => ["analyses", id, "evidence"] as const,
  analysisSources: (id: string) => ["analyses", id, "sources"] as const,
  analysisRecommendations: (id: string) => ["analyses", id, "recommendations"] as const,

  reports: (params?: Record<string, unknown>) => ["reports", params ?? {}] as const,
  report: (id: string) => ["reports", id] as const,

  notifications: (params?: Record<string, unknown>) => ["notifications", params ?? {}] as const,

  history: (params?: Record<string, unknown>) => ["history", params ?? {}] as const,

  dashboardSummary: (params?: Record<string, unknown>) => ["dashboard", "summary", params ?? {}] as const,
  dashboardTrend: (params?: Record<string, unknown>) => ["dashboard", "trend", params ?? {}] as const,
  dashboardSeverity: (params?: Record<string, unknown>) => ["dashboard", "severity", params ?? {}] as const,
  dashboardFailureCategories: (params?: Record<string, unknown>) =>
    ["dashboard", "failure-categories", params ?? {}] as const,
  dashboardRecentIncidents: (params?: Record<string, unknown>) =>
    ["dashboard", "recent-incidents", params ?? {}] as const,
  dashboardActiveAnalyses: (params?: Record<string, unknown>) =>
    ["dashboard", "active-analyses", params ?? {}] as const,
  dashboardActivity: (params?: Record<string, unknown>) => ["dashboard", "activity", params ?? {}] as const,
};
