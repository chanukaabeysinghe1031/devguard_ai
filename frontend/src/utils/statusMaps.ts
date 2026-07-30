/** Central mapping of backend status/severity enums to labels and badge tones. */

export type BadgeTone = "success" | "warning" | "danger" | "info" | "neutral" | "primary" | "secondary";

export interface StatusMeta {
  label: string;
  tone: BadgeTone;
}

const INCIDENT_STATUS_MAP: Record<string, StatusMeta> = {
  detected: { label: "Detected", tone: "info" },
  analysing: { label: "Analysing", tone: "info" },
  open: { label: "Open", tone: "warning" },
  in_progress: { label: "In Progress", tone: "primary" },
  resolved: { label: "Resolved", tone: "success" },
  closed: { label: "Closed", tone: "neutral" },
  analysis_failed: { label: "Analysis Failed", tone: "danger" },
  ignored: { label: "Ignored", tone: "neutral" },
  false_positive: { label: "False Positive", tone: "neutral" },
  reopened: { label: "Reopened", tone: "warning" },
};

const INCIDENT_SEVERITY_MAP: Record<string, StatusMeta> = {
  critical: { label: "Critical", tone: "danger" },
  high: { label: "High", tone: "warning" },
  medium: { label: "Medium", tone: "info" },
  low: { label: "Low", tone: "neutral" },
};

const INCIDENT_PRIORITY_MAP: Record<string, StatusMeta> = {
  urgent: { label: "Urgent", tone: "danger" },
  high: { label: "High", tone: "warning" },
  normal: { label: "Normal", tone: "info" },
  low: { label: "Low", tone: "neutral" },
};

const ANALYSIS_STATUS_MAP: Record<string, StatusMeta> = {
  queued: { label: "Queued", tone: "neutral" },
  preprocessing: { label: "Preprocessing", tone: "info" },
  classifying: { label: "Classifying", tone: "info" },
  retrieving: { label: "Retrieving", tone: "info" },
  reasoning: { label: "Reasoning", tone: "primary" },
  completed: { label: "Completed", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
};

const PIPELINE_RUN_STATUS_MAP: Record<string, StatusMeta> = {
  queued: { label: "Queued", tone: "neutral" },
  running: { label: "Running", tone: "info" },
  succeeded: { label: "Succeeded", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

const PROJECT_STATUS_MAP: Record<string, StatusMeta> = {
  active: { label: "Active", tone: "success" },
  paused: { label: "Paused", tone: "warning" },
  archived: { label: "Archived", tone: "neutral" },
};

const NOTIFICATION_SEVERITY_MAP: Record<string, StatusMeta> = {
  critical: { label: "Critical", tone: "danger" },
  high: { label: "High", tone: "warning" },
  medium: { label: "Medium", tone: "info" },
  low: { label: "Low", tone: "neutral" },
  info: { label: "Info", tone: "info" },
};

const REPORT_STATUS_MAP: Record<string, StatusMeta> = {
  pending: { label: "Pending", tone: "neutral" },
  generating: { label: "Generating", tone: "info" },
  completed: { label: "Completed", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
};

const FALLBACK: StatusMeta = { label: "Unknown", tone: "neutral" };

function lookup(map: Record<string, StatusMeta>, key: string | null | undefined): StatusMeta {
  if (!key) return FALLBACK;
  return map[key] ?? { label: key, tone: "neutral" };
}

export const getIncidentStatusMeta = (status: string | null | undefined): StatusMeta =>
  lookup(INCIDENT_STATUS_MAP, status);

export const getIncidentSeverityMeta = (severity: string | null | undefined): StatusMeta =>
  lookup(INCIDENT_SEVERITY_MAP, severity);

export const getIncidentPriorityMeta = (priority: string | null | undefined): StatusMeta =>
  lookup(INCIDENT_PRIORITY_MAP, priority);

export const getAnalysisStatusMeta = (status: string | null | undefined): StatusMeta =>
  lookup(ANALYSIS_STATUS_MAP, status);

export const getPipelineRunStatusMeta = (status: string | null | undefined): StatusMeta =>
  lookup(PIPELINE_RUN_STATUS_MAP, status);

export const getProjectStatusMeta = (status: string | null | undefined): StatusMeta =>
  lookup(PROJECT_STATUS_MAP, status);

export const getNotificationSeverityMeta = (severity: string | null | undefined): StatusMeta =>
  lookup(NOTIFICATION_SEVERITY_MAP, severity);

export const getReportStatusMeta = (status: string | null | undefined): StatusMeta =>
  lookup(REPORT_STATUS_MAP, status);

export function confidenceTone(confidence: number | null | undefined): BadgeTone {
  if (confidence === null || confidence === undefined) return "neutral";
  const pct = confidence <= 1 ? confidence * 100 : confidence;
  if (pct >= 75) return "success";
  if (pct >= 45) return "warning";
  return "danger";
}

export const ANALYSIS_STAGE_ORDER = [
  "queued",
  "preprocessing",
  "classifying",
  "retrieving",
  "reasoning",
  "completed",
];
