import { Badge } from "./Badge";
import { Tooltip } from "./Tooltip";
import { formatConfidence } from "../../utils/formatters";
import { confidenceTone } from "../../utils/statusMaps";
import { confidenceBandLabel } from "../../utils/executionModeLabels";

const CONFIDENCE_HELP =
  "Heuristic diagnosis confidence from rules and routing — not a calibrated statistical probability of correctness.";

export function ConfidenceBadge({
  confidence,
  band,
  className,
}: {
  confidence: number | null | undefined;
  band?: string | null;
  className?: string;
}) {
  if (confidence === null || confidence === undefined) {
    return (
      <Badge tone="neutral" className={className}>
        No confidence data
      </Badge>
    );
  }

  const label = band ? confidenceBandLabel(band) : `${formatConfidence(confidence)} confidence`;

  return (
    <Tooltip content={CONFIDENCE_HELP}>
      <Badge
        tone={confidenceTone(confidence)}
        className={className}
        title={`${CONFIDENCE_HELP} Score: ${formatConfidence(confidence)}.`}
      >
        {label}
      </Badge>
    </Tooltip>
  );
}
