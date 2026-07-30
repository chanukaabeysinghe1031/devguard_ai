import { useRef, useState } from "react";
import { Bell } from "lucide-react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import * as notificationsApi from "../../api/notificationsApi";
import { queryKeys } from "../../api/queryKeys";
import { useClickOutside } from "../../hooks/useClickOutside";
import { formatRelativeTime } from "../../utils/formatters";
import { EmptyState } from "../ui/EmptyState";
import { Spinner } from "../ui/Spinner";

export function NotificationMenu() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  useClickOutside(containerRef, () => setOpen(false), open);

  const params = { page: 1, page_size: 6 };
  const { data, isLoading } = useQuery({
    queryKey: queryKeys.notifications(params),
    queryFn: () => notificationsApi.listNotifications(params),
    refetchInterval: 60_000,
  });

  const unreadCount = data?.unread_count ?? 0;

  const handleMarkAllRead = async () => {
    await notificationsApi.markAllNotificationsRead();
    await queryClient.invalidateQueries({ queryKey: ["notifications"] });
  };

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ""}`}
        className="relative flex h-10 w-10 items-center justify-center rounded-md text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute right-1.5 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-semibold text-white">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-80 rounded-md border border-border-strong bg-surface-elevated shadow-elevated"
        >
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <p className="text-sm font-semibold text-text-primary">Notifications</p>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={handleMarkAllRead}
                className="text-xs font-medium text-primary hover:underline"
              >
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-y-auto">
            {isLoading && (
              <div className="flex justify-center py-6">
                <Spinner size="sm" />
              </div>
            )}
            {!isLoading && (data?.items.length ?? 0) === 0 && (
              <div className="px-4 py-6">
                <EmptyState title="No notifications" description="You're all caught up." />
              </div>
            )}
            {!isLoading &&
              data?.items.map((notification) => (
                <div
                  key={notification.id}
                  className="flex flex-col gap-0.5 border-b border-border px-4 py-3 last:border-b-0 hover:bg-surface-hover"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium text-text-primary">{notification.title}</p>
                    {!notification.is_read && <span className="h-2 w-2 shrink-0 rounded-full bg-primary" />}
                  </div>
                  <p className="line-clamp-2 text-xs text-text-muted">{notification.message}</p>
                  <p className="text-[11px] text-text-disabled">{formatRelativeTime(notification.created_at)}</p>
                </div>
              ))}
          </div>
          <Link
            to="/notifications"
            onClick={() => setOpen(false)}
            className="block border-t border-border px-4 py-2.5 text-center text-sm font-medium text-primary hover:bg-surface-hover"
          >
            View all notifications
          </Link>
        </div>
      )}
    </div>
  );
}
