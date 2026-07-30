import { FileText } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { listReports } from "../../api/reportsApi";
import { queryKeys } from "../../api/queryKeys";
import { DataTable, type DataTableColumn } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorRetryAlert } from "../../components/ui/Alert";
import { PageHeader } from "../../components/ui/PageHeader";
import { StatusBadge } from "../../components/ui/StatusBadge";
import type { ReportListItem } from "../../types/report";
import { formatDateTime } from "../../utils/formatters";

export function ReportsListPage() {
  const navigate = useNavigate();
  const params = { page: 1, page_size: 30 };
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.reports(params),
    queryFn: () => listReports(params),
  });

  const columns: Array<DataTableColumn<ReportListItem>> = [
    {
      key: "incident",
      header: "Incident",
      render: (report) => (
        <div>
          <p className="font-medium text-text-primary">{report.incident_title}</p>
          <p className="text-xs text-text-muted">{report.incident_number}</p>
        </div>
      ),
    },
    { key: "format", header: "Format", render: (report) => report.format.toUpperCase() },
    { key: "version", header: "Version", render: (report) => `v${report.version}` },
    { key: "status", header: "Status", render: (report) => <StatusBadge kind="report" status={report.generation_status} /> },
    { key: "created_at", header: "Generated", render: (report) => formatDateTime(report.created_at) },
  ];

  return (
    <div>
      <PageHeader title="Reports" description="Generated incident reports across your organization." />

      {isError ? (
        <ErrorRetryAlert message="Failed to load reports." onRetry={() => refetch()} />
      ) : !isLoading && data?.items.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No reports yet"
          description="Generate a report from an incident's Report tab to see it here."
        />
      ) : (
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(row) => row.id}
          isLoading={isLoading}
          onRowClick={(row) => navigate(`/reports/${row.id}`)}
        />
      )}
    </div>
  );
}
