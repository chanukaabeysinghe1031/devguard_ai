import { CheckCircle2, Database, Server, XCircle } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "../../api/client";
import { Card, CardBody } from "../../components/ui/Card";
import { PageHeader } from "../../components/ui/PageHeader";
import { Skeleton } from "../../components/ui/Skeleton";

interface LivenessResponse {
  status: string;
  service: string;
  version: string;
}

interface ReadinessResponse {
  status: string;
  database: string;
}

export function SystemHealthPage() {
  const livenessQuery = useQuery({
    queryKey: ["system-health", "liveness"],
    queryFn: () => apiFetch<LivenessResponse>("/health"),
    refetchInterval: 30_000,
  });

  const readinessQuery = useQuery({
    queryKey: ["system-health", "readiness"],
    queryFn: () => apiFetch<ReadinessResponse>("/health/ready"),
    refetchInterval: 30_000,
    retry: false,
  });

  return (
    <div>
      <PageHeader title="System health" description="Live backend service and database connectivity status." />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card>
          <CardBody className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/15 text-primary">
                <Server className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-medium text-text-muted">API service</p>
                {livenessQuery.isLoading ? (
                  <Skeleton className="mt-1 h-5 w-24" />
                ) : (
                  <p className="text-base font-semibold text-text-primary">
                    {livenessQuery.data?.service ?? "Unknown"} v{livenessQuery.data?.version ?? "—"}
                  </p>
                )}
              </div>
            </div>
            {livenessQuery.isError ? (
              <XCircle className="h-6 w-6 text-danger" />
            ) : livenessQuery.isLoading ? null : (
              <CheckCircle2 className="h-6 w-6 text-success" />
            )}
          </CardBody>
        </Card>

        <Card>
          <CardBody className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-secondary/15 text-secondary">
                <Database className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-medium text-text-muted">Database connectivity</p>
                {readinessQuery.isLoading ? (
                  <Skeleton className="mt-1 h-5 w-24" />
                ) : (
                  <p className="text-base font-semibold text-text-primary">
                    {readinessQuery.isError ? "Unavailable" : titleCaseStatus(readinessQuery.data?.database)}
                  </p>
                )}
              </div>
            </div>
            {readinessQuery.isError ? (
              <XCircle className="h-6 w-6 text-danger" />
            ) : readinessQuery.isLoading ? null : (
              <CheckCircle2 className="h-6 w-6 text-success" />
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function titleCaseStatus(value: string | undefined): string {
  if (!value) return "Unknown";
  return value.charAt(0).toUpperCase() + value.slice(1);
}
