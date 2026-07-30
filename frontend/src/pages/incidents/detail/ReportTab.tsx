import { useState } from "react";
import { FileText } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { generateIncidentReport } from "../../../api/incidentsApi";
import { listReports } from "../../../api/reportsApi";
import { queryKeys } from "../../../api/queryKeys";
import { Alert } from "../../../components/ui/Alert";
import { Button } from "../../../components/ui/Button";
import { Card, CardBody } from "../../../components/ui/Card";
import { EmptyState } from "../../../components/ui/EmptyState";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { SkeletonCard } from "../../../components/ui/Skeleton";
import { formatDateTime } from "../../../utils/formatters";

export function ReportTab({ incidentId }: { incidentId: string }) {
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);

  const params = { incident_id: incidentId, page: 1, page_size: 20 };
  const reportsQuery = useQuery({
    queryKey: queryKeys.reports(params),
    queryFn: () => listReports(params),
  });

  const generateMutation = useMutation({
    mutationFn: () => generateIncidentReport(incidentId, { format: "json" }),
    onSuccess: async () => {
      setServerError(null);
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
    onError: (error) => setServerError(error instanceof ApiError ? error.message : "Failed to generate report."),
  });

  return (
    <div className="flex flex-col gap-4">
      {serverError && <Alert variant="danger">{serverError}</Alert>}

      <div className="flex justify-end">
        <Button onClick={() => generateMutation.mutate()} isLoading={generateMutation.isPending}>
          Generate report
        </Button>
      </div>

      {reportsQuery.isLoading ? (
        <SkeletonCard />
      ) : !reportsQuery.data?.items.length ? (
        <EmptyState icon={FileText} title="No reports yet" description="Generate a report to create a shareable incident summary." />
      ) : (
        <div className="flex flex-col gap-3">
          {reportsQuery.data.items.map((report) => (
            <Card key={report.id}>
              <CardBody>
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <Link to={`/reports/${report.id}`} className="text-sm font-semibold text-text-primary hover:underline">
                      Report v{report.version} · {report.format.toUpperCase()}
                    </Link>
                    <p className="mt-0.5 text-xs text-text-muted">{formatDateTime(report.created_at)}</p>
                  </div>
                  <StatusBadge kind="report" status={report.generation_status} />
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
