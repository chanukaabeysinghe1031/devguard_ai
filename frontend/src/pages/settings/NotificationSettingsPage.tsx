import { BellOff } from "lucide-react";

import { EmptyState } from "../../components/ui/EmptyState";

export function NotificationSettingsPage() {
  return (
    <EmptyState
      icon={BellOff}
      title="Notification preferences coming soon"
      description="Per-channel notification preferences are not yet available. In-app notifications are enabled by default."
    />
  );
}
