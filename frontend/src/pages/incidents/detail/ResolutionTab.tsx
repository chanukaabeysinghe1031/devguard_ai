import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { ApiError } from "../../../api/client";
import { reopenIncident, resolveIncident, listIncidentResolutions } from "../../../api/incidentsApi";
import { queryKeys } from "../../../api/queryKeys";
import { Alert } from "../../../components/ui/Alert";
import { Button } from "../../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../../components/ui/Card";
import { EmptyState } from "../../../components/ui/EmptyState";
import { Input } from "../../../components/ui/Input";
import { SkeletonCard } from "../../../components/ui/Skeleton";
import { Textarea } from "../../../components/ui/Textarea";
import type { IncidentDetail } from "../../../types/incident";
import { formatDateTime } from "../../../utils/formatters";

const resolveSchema = z.object({
  resolution_summary: z.string().min(1, "Summary is required"),
  confirmed_root_cause: z.string().min(1, "Root cause is required"),
  resolution_steps: z.string().optional().or(z.literal("")),
  prevention_actions: z.string().optional().or(z.literal("")),
  time_spent_minutes: z.string().optional().or(z.literal("")),
});
type ResolveFormValues = z.infer<typeof resolveSchema>;

const reopenSchema = z.object({ reason: z.string().min(1, "Reason is required") });
type ReopenFormValues = z.infer<typeof reopenSchema>;

const RESOLVED_STATUSES = new Set(["resolved", "closed"]);

function linesToList(value: string | undefined): string[] {
  return (value ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

export function ResolutionTab({ incident, incidentId }: { incident: IncidentDetail; incidentId: string }) {
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const isResolved = RESOLVED_STATUSES.has(incident.status);

  const resolutionsQuery = useQuery({
    queryKey: queryKeys.incidentResolutions(incidentId),
    queryFn: () => listIncidentResolutions(incidentId),
  });

  const invalidateIncident = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.incident(incidentId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.incidentResolutions(incidentId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.incidentTimeline(incidentId) });
  };

  const resolveForm = useForm<ResolveFormValues>({ resolver: zodResolver(resolveSchema) });
  const reopenForm = useForm<ReopenFormValues>({ resolver: zodResolver(reopenSchema) });

  const resolveMutation = useMutation({
    mutationFn: (values: ResolveFormValues) =>
      resolveIncident(incidentId, {
        resolution_summary: values.resolution_summary,
        confirmed_root_cause: values.confirmed_root_cause,
        resolution_steps: linesToList(values.resolution_steps),
        prevention_actions: linesToList(values.prevention_actions),
        time_spent_minutes: values.time_spent_minutes ? Number(values.time_spent_minutes) : undefined,
      }),
    onSuccess: () => {
      resolveForm.reset();
      invalidateIncident();
    },
    onError: (error) => setServerError(error instanceof ApiError ? error.message : "Failed to resolve incident."),
  });

  const reopenMutation = useMutation({
    mutationFn: (values: ReopenFormValues) => reopenIncident(incidentId, values),
    onSuccess: () => {
      reopenForm.reset();
      invalidateIncident();
    },
    onError: (error) => setServerError(error instanceof ApiError ? error.message : "Failed to reopen incident."),
  });

  return (
    <div className="flex flex-col gap-4">
      {serverError && <Alert variant="danger">{serverError}</Alert>}

      {isResolved ? (
        <Card>
          <CardHeader title="Reopen incident" subtitle="This incident has been resolved." />
          <CardBody>
            <form
              onSubmit={reopenForm.handleSubmit((values) => {
                setServerError(null);
                reopenMutation.mutate(values);
              })}
              className="flex flex-col gap-3"
            >
              <Textarea
                label="Reason for reopening"
                required
                error={reopenForm.formState.errors.reason?.message}
                {...reopenForm.register("reason")}
              />
              <div className="flex justify-end">
                <Button type="submit" variant="outline" isLoading={reopenMutation.isPending}>
                  Reopen incident
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>
      ) : (
        <Card>
          <CardHeader title="Resolve incident" />
          <CardBody>
            <form
              onSubmit={resolveForm.handleSubmit((values) => {
                setServerError(null);
                resolveMutation.mutate(values);
              })}
              className="flex flex-col gap-3"
            >
              <Textarea
                label="Resolution summary"
                required
                error={resolveForm.formState.errors.resolution_summary?.message}
                {...resolveForm.register("resolution_summary")}
              />
              <Textarea
                label="Confirmed root cause"
                required
                error={resolveForm.formState.errors.confirmed_root_cause?.message}
                {...resolveForm.register("confirmed_root_cause")}
              />
              <Textarea
                label="Resolution steps"
                hint="One step per line"
                {...resolveForm.register("resolution_steps")}
              />
              <Textarea
                label="Prevention actions"
                hint="One action per line"
                {...resolveForm.register("prevention_actions")}
              />
              <Input
                type="number"
                label="Time spent (minutes)"
                min={0}
                {...resolveForm.register("time_spent_minutes")}
              />
              <div className="flex justify-end">
                <Button type="submit" isLoading={resolveMutation.isPending}>
                  Resolve incident
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader title="Resolution history" />
        <CardBody>
          {resolutionsQuery.isLoading ? (
            <SkeletonCard />
          ) : !resolutionsQuery.data?.length ? (
            <EmptyState title="No resolutions yet" description="Resolution records will appear here." />
          ) : (
            <div className="flex flex-col gap-4">
              {resolutionsQuery.data.map((resolution) => (
                <div key={resolution.id} className="border-b border-border pb-4 last:border-0 last:pb-0">
                  <p className="text-sm font-medium text-text-primary">{resolution.resolution_summary}</p>
                  <p className="mt-1 text-xs text-text-muted">Root cause: {resolution.confirmed_root_cause}</p>
                  {resolution.resolution_steps && resolution.resolution_steps.length > 0 && (
                    <ul className="mt-2 list-disc pl-5 text-xs text-text-secondary">
                      {resolution.resolution_steps.map((step, index) => (
                        <li key={index}>{step}</li>
                      ))}
                    </ul>
                  )}
                  <p className="mt-2 text-xs text-text-disabled">{formatDateTime(resolution.created_at)}</p>
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
