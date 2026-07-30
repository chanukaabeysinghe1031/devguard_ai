import { useState } from "react";
import { Cog, X } from "lucide-react";

import { Badge } from "../../../components/ui/Badge";
import { KeyValueList } from "../../../components/ui/KeyValueList";
import type { AnalysisRunDetail } from "../../../types/analysis";
import { formatConfidence, formatDurationMs } from "../../../utils/formatters";

/**
 * Admin-only technical diagnostics drawer. Shows the raw Module 8/9
 * orchestration route/mode data that must not be exposed to regular users.
 */
export function DiagnosticsDrawer({ analysis }: { analysis: AnalysisRunDetail | undefined }) {
  const [open, setOpen] = useState(false);

  if (!analysis?.orchestration) return null;
  const orchestration = analysis.orchestration;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 rounded-md border border-border-strong px-3 py-1.5 text-xs font-medium text-text-muted transition-colors hover:bg-surface-hover hover:text-text-primary"
      >
        <Cog className="h-3.5 w-3.5" />
        Diagnostics
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/60" onClick={() => setOpen(false)}>
          <div
            className="h-full w-full max-w-md overflow-y-auto border-l border-border-strong bg-surface-elevated p-5"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold text-text-primary">Orchestration diagnostics</h3>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close diagnostics"
                className="rounded-md p-1 text-text-muted hover:bg-surface-hover hover:text-text-primary"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="mb-4 text-xs text-text-muted">
              Internal routing metadata for debugging and research evaluation. Not shown to non-admin users.
            </p>
            <KeyValueList
              items={[
                { label: "Requested execution mode", value: orchestration.requested_execution_mode ?? "—" },
                { label: "Effective execution mode", value: orchestration.effective_execution_mode ?? "—" },
                { label: "Selected route", value: orchestration.selected_route ?? "—" },
                { label: "Routing policy version", value: orchestration.routing_policy_version ?? "—" },
                { label: "Confidence", value: formatConfidence(orchestration.confidence) },
                { label: "Confidence band", value: orchestration.confidence_band ?? "—" },
                { label: "Uncertainty score", value: orchestration.uncertainty_score?.toFixed(3) ?? "—" },
                { label: "Uncertainty level", value: orchestration.uncertainty_level ?? "—" },
                { label: "Evidence quality score", value: orchestration.evidence_quality_score?.toFixed(3) ?? "—" },
                {
                  label: "Retrieval used",
                  value: <Badge tone={orchestration.retrieval_used ? "success" : "neutral"}>{String(orchestration.retrieval_used)}</Badge>,
                },
                {
                  label: "Reasoning used",
                  value: <Badge tone={orchestration.reasoning_used ? "success" : "neutral"}>{String(orchestration.reasoning_used)}</Badge>,
                },
                {
                  label: "Fallback used",
                  value: <Badge tone={orchestration.fallback_used ? "warning" : "neutral"}>{String(orchestration.fallback_used)}</Badge>,
                },
                { label: "Fallback reason", value: orchestration.fallback_reason ?? "—" },
                { label: "Retrieval mode", value: orchestration.retrieval_mode ?? "—" },
                { label: "Retrieval quality score", value: orchestration.retrieval_quality_score?.toFixed(3) ?? "—" },
                { label: "Candidates considered", value: orchestration.candidates_considered ?? "—" },
                { label: "Results selected", value: orchestration.results_selected ?? "—" },
                { label: "Duplicate count", value: orchestration.duplicate_count ?? "—" },
                { label: "Historical results used", value: orchestration.historical_results_used ?? "—" },
                {
                  label: "Retrieval fallback used",
                  value: (
                    <Badge tone={orchestration.retrieval_fallback_used ? "warning" : "neutral"}>
                      {String(orchestration.retrieval_fallback_used)}
                    </Badge>
                  ),
                },
                { label: "Retrieval fallback reason", value: orchestration.retrieval_fallback_reason ?? "—" },
                { label: "Retrieval config hash", value: orchestration.retrieval_configuration_hash ?? "—" },
                { label: "Processing time", value: formatDurationMs(analysis.processing_time_ms) },
              ]}
            />
          </div>
        </div>
      )}
    </>
  );
}
