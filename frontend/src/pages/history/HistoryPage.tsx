import { useState } from "react";
import { History } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { searchIncidentHistory } from "../../api/historyApi";
import { queryKeys } from "../../api/queryKeys";
import { DataTable, type DataTableColumn } from "../../components/ui/DataTable";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorRetryAlert } from "../../components/ui/Alert";
import { PageHeader } from "../../components/ui/PageHeader";
import { SearchInput } from "../../components/ui/SearchInput";
import { SeverityBadge } from "../../components/ui/SeverityBadge";
import { StatusBadge } from "../../components/ui/StatusBadge";
import type { HistoryIncidentItem } from "../../types/history";
import { formatDate, formatRelativeTime } from "../../utils/formatters";

export function HistoryPage() {
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  const params = { page: 1, page_size: 30, search: search || undefined };
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.history(params),
    queryFn: () => searchIncidentHistory(params),
  });

  const columns: Array<DataTableColumn<HistoryIncidentItem>> = [
    {
      key: "title",
      header: "Incident",
      render: (item) => (
        <div>
          <p className="font-medium text-text-primary">{item.title}</p>
          <p className="text-xs text-text-muted">{item.incident_number}</p>
        </div>
      ),
    },
    { key: "project", header: "Project", render: (item) => item.project.name },
    { key: "severity", header: "Severity", render: (item) => <SeverityBadge severity={item.severity} /> },
    { key: "status", header: "Status", render: (item) => <StatusBadge kind="incident" status={item.status} /> },
    { key: "category", header: "Category", render: (item) => item.predicted_category ?? "—" },
    { key: "detected_at", header: "Detected", render: (item) => formatDate(item.detected_at) },
    { key: "resolved_at", header: "Resolved", render: (item) => formatRelativeTime(item.resolved_at) },
  ];

  return (
    <div>
      <PageHeader title="History" description="Search and review the full incident history for your organization." />

      <div className="mb-4 max-w-sm">
        <SearchInput value={search} onChange={setSearch} placeholder="Search history…" />
      </div>

      {isError ? (
        <ErrorRetryAlert message="Failed to load history." onRetry={() => refetch()} />
      ) : !isLoading && data?.items.length === 0 ? (
        <EmptyState icon={History} title="No history yet" description="Resolved and past incidents will appear here." />
      ) : (
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(row) => row.id}
          isLoading={isLoading}
          onRowClick={(row) => navigate(`/incidents/${row.id}`)}
        />
      )}
    </div>
  );
}
