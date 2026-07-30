import { useQuery } from "@tanstack/react-query";

import { getAnalysis } from "../../../api/analysesApi";
import { queryKeys } from "../../../api/queryKeys";
import { Alert } from "../../../components/ui/Alert";
import { Card, CardBody, CardHeader } from "../../../components/ui/Card";
import { ConfidenceBadge } from "../../../components/ui/ConfidenceBadge";
import { KeyValueList } from "../../../components/ui/KeyValueList";
import { Skeleton } from "../../../components/ui/Skeleton";
import { useAuth } from "../../../hooks/useAuth";
import type { IncidentDetail } from "../../../types/incident";
import { effectiveDiagnosisLabel } from "../../../utils/executionModeLabels";
import { formatDateTime, titleCase } from "../../../utils/formatters";
import { DiagnosticsDrawer } from "./DiagnosticsDrawer";

export function OverviewTab({ incident, analysisId }: { incident: IncidentDetail; analysisId: string | null }) {
  const { hasAnyRole } = useAuth();
  const isAdmin = hasAnyRole(["organization_owner", "organization_admin"]);

  const analysisQuery = useQuery({
    queryKey: queryKeys.analysis(analysisId ?? ""),
    queryFn: () => getAnalysis(analysisId!),
    enabled: Boolean(analysisId),
  });

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader title="Incident details" />
        <CardBody>
          <KeyValueList
            columns={2}
            items={[
              { label: "Project", value: incident.project.name },
              { label: "Environment", value: incident.environment ? titleCase(incident.environment) : "—" },
              { label: "Source", value: titleCase(incident.source) },
              { label: "Detected", value: formatDateTime(incident.detected_at) },
              { label: "Acknowledged", value: formatDateTime(incident.acknowledged_at) },
              { label: "Resolved", value: formatDateTime(incident.resolved_at) },
            ]}
          />
          {incident.description && (
            <p className="mt-4 whitespace-pre-wrap text-sm text-text-secondary">{incident.description}</p>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="AI analysis summary"
          action={isAdmin && <DiagnosticsDrawer analysis={analysisQuery.data} />}
        />
        <CardBody>
          {!analysisId ? (
            <Alert variant="info">No analysis has been run for this incident yet.</Alert>
          ) : analysisQuery.isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : analysisQuery.isError ? (
            <Alert variant="danger">Failed to load analysis summary.</Alert>
          ) : (
            <div className="flex flex-col gap-4">
              <div className="flex flex-wrap items-center gap-2">
                <ConfidenceBadge
                  confidence={
                    analysisQuery.data?.orchestration?.confidence ??
                    analysisQuery.data?.classification?.confidence ??
                    analysisQuery.data?.root_cause?.confidence
                  }
                  band={analysisQuery.data?.orchestration?.confidence_band}
                />
                <span className="rounded-full border border-border-strong bg-surface-interactive px-2.5 py-0.5 text-xs font-medium text-text-secondary">
                  {effectiveDiagnosisLabel(analysisQuery.data?.orchestration)}
                </span>
              </div>

              {analysisQuery.data?.classification?.category && (
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-text-muted">Predicted category</p>
                  <p className="mt-0.5 text-sm text-text-primary">
                    {titleCase(analysisQuery.data.classification.category)}
                  </p>
                </div>
              )}

              {analysisQuery.data?.root_cause?.summary && (
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-text-muted">Root cause</p>
                  <p className="mt-0.5 whitespace-pre-wrap text-sm text-text-primary">
                    {analysisQuery.data.root_cause.summary}
                  </p>
                </div>
              )}

              {analysisQuery.data && analysisQuery.data.limitations.length > 0 && (
                <Alert variant="warning" title="Limitations">
                  <ul className="list-disc pl-4">
                    {analysisQuery.data.limitations.map((limitation, index) => (
                      <li key={index}>{limitation}</li>
                    ))}
                  </ul>
                </Alert>
              )}

              <KeyValueList
                columns={2}
                items={[
                  { label: "Evidence items", value: analysisQuery.data?.evidence_count ?? 0 },
                  { label: "Recommendations", value: analysisQuery.data?.recommendation_count ?? 0 },
                  { label: "Retrieved sources", value: analysisQuery.data?.retrieved_document_count ?? 0 },
                ]}
              />
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
