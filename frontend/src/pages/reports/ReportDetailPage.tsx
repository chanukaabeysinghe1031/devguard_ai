import { useState } from "react";
import { Download } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { fetchReportBlob, getReport } from "../../api/reportsApi";
import { queryKeys } from "../../api/queryKeys";
import { Alert, ErrorRetryAlert } from "../../components/ui/Alert";
import { Breadcrumbs } from "../../components/ui/Breadcrumbs";
import { Button } from "../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { CodeBlock } from "../../components/ui/CodeBlock";
import { KeyValueList } from "../../components/ui/KeyValueList";
import { PageHeader } from "../../components/ui/PageHeader";
import { Skeleton } from "../../components/ui/Skeleton";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { formatDateTime } from "../../utils/formatters";

export function ReportDetailPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);

  const reportQuery = useQuery({
    queryKey: queryKeys.report(reportId ?? ""),
    queryFn: () => getReport(reportId!),
    enabled: Boolean(reportId),
  });

  const handleDownload = async () => {
    if (!reportId) return;
    setDownloadError(null);
    setIsDownloading(true);
    try {
      const blob = await fetchReportBlob(reportId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `incident-report-${reportId}.${reportQuery.data?.format ?? "json"}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setDownloadError("Failed to download report.");
    } finally {
      setIsDownloading(false);
    }
  };

  if (reportQuery.isLoading) {
    return <Skeleton className="h-72 w-full" />;
  }

  if (reportQuery.isError || !reportQuery.data) {
    return <ErrorRetryAlert message="Failed to load report." onRetry={() => reportQuery.refetch()} />;
  }

  const report = reportQuery.data;

  return (
    <div>
      <PageHeader
        title={`Report v${report.version}`}
        breadcrumbs={<Breadcrumbs items={[{ label: "Reports", to: "/reports" }, { label: `v${report.version}` }]} />}
        actions={
          <Button leftIcon={<Download className="h-4 w-4" />} onClick={handleDownload} isLoading={isDownloading}>
            Download
          </Button>
        }
      />

      {downloadError && (
        <Alert variant="danger" className="mb-4">
          {downloadError}
        </Alert>
      )}

      <Card>
        <CardHeader title="Report details" action={<StatusBadge kind="report" status={report.generation_status} />} />
        <CardBody>
          <KeyValueList
            columns={2}
            items={[
              { label: "Format", value: report.format.toUpperCase() },
              { label: "Version", value: report.version },
              { label: "Generated", value: formatDateTime(report.created_at) },
              {
                label: "Incident",
                value: (
                  <Link to={`/incidents/${report.incident_id}`} className="text-primary hover:underline">
                    View incident
                  </Link>
                ),
              },
            ]}
          />
        </CardBody>
      </Card>

      {report.content && (
        <Card className="mt-6">
          <CardHeader title="Report content" />
          <CardBody>
            <CodeBlock language="json" code={JSON.stringify(report.content, null, 2)} maxHeight="32rem" />
          </CardBody>
        </Card>
      )}
    </div>
  );
}
