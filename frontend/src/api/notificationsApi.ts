import { apiFetch } from "./client";
import { buildQueryString } from "./queryString";
import type { MessageResponse } from "../types/common";
import type { NotificationListResponse } from "../types/notification";

export interface ListNotificationsParams {
  page?: number;
  page_size?: number;
  is_read?: boolean;
  severity?: string;
  notification_type?: string;
  incident_id?: string;
}

export async function listNotifications(
  params: ListNotificationsParams = {},
): Promise<NotificationListResponse> {
  return apiFetch<NotificationListResponse>(`/notifications${buildQueryString(params)}`);
}

export async function markNotificationRead(notificationId: string) {
  return apiFetch(`/notifications/${notificationId}/read`, { method: "POST" });
}

export async function markAllNotificationsRead(): Promise<MessageResponse> {
  return apiFetch<MessageResponse>("/notifications/read-all", { method: "POST" });
}

export async function deleteNotification(notificationId: string): Promise<void> {
  await apiFetch<void>(`/notifications/${notificationId}`, { method: "DELETE" });
}
