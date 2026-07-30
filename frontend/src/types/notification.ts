export interface AppNotification {
  id: string;
  notification_type: string;
  title: string;
  message: string;
  severity: string | null;
  channel: string;
  delivery_status: string;
  is_read: boolean;
  incident_id: string | null;
  created_at: string;
  read_at: string | null;
}

export interface NotificationListResponse {
  items: AppNotification[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  unread_count: number;
}
