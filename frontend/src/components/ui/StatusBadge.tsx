import { Badge } from "./Badge";
import {
  getAnalysisStatusMeta,
  getIncidentStatusMeta,
  getPipelineRunStatusMeta,
  getProjectStatusMeta,
  getReportStatusMeta,
} from "../../utils/statusMaps";

type StatusKind = "incident" | "analysis" | "pipeline" | "project" | "report";

const RESOLVERS: Record<StatusKind, (value: string | null | undefined) => { label: string; tone: import("../../utils/statusMaps").BadgeTone }> = {
  incident: getIncidentStatusMeta,
  analysis: getAnalysisStatusMeta,
  pipeline: getPipelineRunStatusMeta,
  project: getProjectStatusMeta,
  report: getReportStatusMeta,
};

export function StatusBadge({
  kind,
  status,
  className,
}: {
  kind: StatusKind;
  status: string | null | undefined;
  className?: string;
}) {
  const meta = RESOLVERS[kind](status);
  return (
    <Badge tone={meta.tone} dot className={className}>
      {meta.label}
    </Badge>
  );
}
