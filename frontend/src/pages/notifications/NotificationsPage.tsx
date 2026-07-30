import { useState } from "react";
import { Bell, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import * as notificationsApi from "../../api/notificationsApi";
import { queryKeys } from "../../api/queryKeys";
import { Button } from "../../components/ui/Button";
import { Card, CardBody } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorRetryAlert } from "../../components/ui/Alert";
import { PageHeader } from "../../components/ui/PageHeader";
import { Select } from "../../components/ui/Select";
import { formatDateTime } from "../../utils/formatters";
import { getNotificationSeverityMeta } from "../../utils/statusMaps";
import { Badge } from "../../components/ui/Badge";

const FILTER_OPTIONS = [
  { value: "", label: "All notifications" },
  { value: "false", label: "Unread" },
  { value: "true", label: "Read" },
];

export function NotificationsPage() {
  const [filter, setFilter] = useState("");
  const queryClient = useQueryClient();

  const params = { page: 1, page_size: 30, is_read: filter === "" ? undefined : filter === "true" };
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.notifications(params),
    queryFn: () => notificationsApi.listNotifications(params),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["notifications"] });

  const markReadMutation = useMutation({
    mutationFn: (id: string) => notificationsApi.markNotificationRead(id),
    onSuccess: invalidate,
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => notificationsApi.markAllNotificationsRead(),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => notificationsApi.deleteNotification(id),
    onSuccess: invalidate,
  });

  return (
    <div>
      <PageHeader
        title="Notifications"
        description="Analysis completions, assignments, and system alerts."
        actions={
          <Button variant="outline" onClick={() => markAllReadMutation.mutate()} isLoading={markAllReadMutation.isPending}>
            Mark all read
          </Button>
        }
      />

      <div className="mb-4 max-w-xs">
        <Select options={FILTER_OPTIONS} value={filter} onChange={(event) => setFilter(event.target.value)} />
      </div>

      {isError ? (
        <ErrorRetryAlert message="Failed to load notifications." onRetry={() => refetch()} />
      ) : !isLoading && data?.items.length === 0 ? (
        <EmptyState icon={Bell} title="No notifications" description="You're all caught up." />
      ) : (
        <div className="flex flex-col gap-3">
          {data?.items.map((notification) => {
            const severityMeta = getNotificationSeverityMeta(notification.severity ?? undefined);
            return (
              <Card key={notification.id} className={!notification.is_read ? "border-primary/40" : undefined}>
                <CardBody>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-text-primary">{notification.title}</p>
                        {notification.severity && <Badge tone={severityMeta.tone}>{severityMeta.label}</Badge>}
                        {!notification.is_read && <span className="h-2 w-2 rounded-full bg-primary" />}
                      </div>
                      <p className="mt-1 text-sm text-text-secondary">{notification.message}</p>
                      <p className="mt-1.5 text-xs text-text-disabled">{formatDateTime(notification.created_at)}</p>
                      {notification.incident_id && (
                        <Link
                          to={`/incidents/${notification.incident_id}`}
                          className="mt-1 inline-block text-xs font-medium text-primary hover:underline"
                        >
                          View incident
                        </Link>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      {!notification.is_read && (
                        <Button variant="ghost" size="sm" onClick={() => markReadMutation.mutate(notification.id)}>
                          Mark read
                        </Button>
                      )}
                      <button
                        type="button"
                        onClick={() => deleteMutation.mutate(notification.id)}
                        aria-label="Delete notification"
                        className="rounded p-1.5 text-text-muted hover:bg-danger/10 hover:text-danger"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </CardBody>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
