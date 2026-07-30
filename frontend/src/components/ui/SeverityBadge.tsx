import { Badge } from "./Badge";
import { getIncidentPriorityMeta, getIncidentSeverityMeta } from "../../utils/statusMaps";

export function SeverityBadge({
  severity,
  className,
}: {
  severity: string | null | undefined;
  className?: string;
}) {
  const meta = getIncidentSeverityMeta(severity);
  return (
    <Badge tone={meta.tone} className={className}>
      {meta.label}
    </Badge>
  );
}

export function PriorityBadge({
  priority,
  className,
}: {
  priority: string | null | undefined;
  className?: string;
}) {
  const meta = getIncidentPriorityMeta(priority);
  return (
    <Badge tone={meta.tone} className={className}>
      {meta.label}
    </Badge>
  );
}
