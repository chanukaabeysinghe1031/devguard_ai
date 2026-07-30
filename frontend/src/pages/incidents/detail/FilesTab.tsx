import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";

import { listIncidentFiles } from "../../../api/filesApi";
import { queryKeys } from "../../../api/queryKeys";
import { Badge } from "../../../components/ui/Badge";
import { DataTable, type DataTableColumn } from "../../../components/ui/DataTable";
import { ErrorRetryAlert } from "../../../components/ui/Alert";
import type { UploadedFile } from "../../../types/file";
import { formatDateTime, formatFileSize, titleCase } from "../../../utils/formatters";

function statusTone(status: string): "success" | "warning" | "danger" | "neutral" {
  if (["valid", "masked", "completed"].includes(status)) return "success";
  if (["pending", "processing"].includes(status)) return "warning";
  if (["invalid", "failed"].includes(status)) return "danger";
  return "neutral";
}

export function FilesTab({ incidentId }: { incidentId: string }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.incidentFiles(incidentId),
    queryFn: () => listIncidentFiles(incidentId),
  });

  const columns: Array<DataTableColumn<UploadedFile>> = [
    {
      key: "name",
      header: "File",
      render: (file) => (
        <div>
          <p className="font-medium text-text-primary">{file.original_filename}</p>
          <p className="text-xs text-text-muted">
            {titleCase(file.file_type)} · {formatFileSize(file.size_bytes)}
          </p>
        </div>
      ),
    },
    {
      key: "validation_status",
      header: "Validation",
      render: (file) => <Badge tone={statusTone(file.validation_status)}>{titleCase(file.validation_status)}</Badge>,
    },
    {
      key: "secret_masking_status",
      header: "Secret masking",
      render: (file) => <Badge tone={statusTone(file.secret_masking_status)}>{titleCase(file.secret_masking_status)}</Badge>,
    },
    {
      key: "processing_status",
      header: "Processing",
      render: (file) => <Badge tone={statusTone(file.processing_status)}>{titleCase(file.processing_status)}</Badge>,
    },
    { key: "uploaded_at", header: "Uploaded", render: (file) => formatDateTime(file.uploaded_at) },
  ];

  if (isError) return <ErrorRetryAlert message="Failed to load files." onRetry={() => refetch()} />;

  return (
    <DataTable
      columns={columns}
      rows={data?.items ?? []}
      rowKey={(row) => row.id}
      isLoading={isLoading}
      emptyTitle="No files uploaded"
      emptyDescription="Files uploaded for this incident will appear here."
    />
  );
}

export const FilesTabIcon = FileText;
