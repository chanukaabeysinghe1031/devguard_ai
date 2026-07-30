import { Bell } from "lucide-react";

import { Alert } from "../../components/ui/Alert";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { PageHeader } from "../../components/ui/PageHeader";

export function NotificationSettingsPage() {
  return (
    <div>
      <PageHeader
        title="Notification preferences"
        description="How DevGuard AI notifies you inside the product."
      />
      <Alert variant="info">
        Per-user channel preferences are not stored yet. In-app notifications are always enabled for
        assignment, analysis completion/failure, and resolution events.
      </Alert>
      <Card className="mt-4">
        <CardHeader title="Current behaviour (read-only)" />
        <CardBody>
          <ul className="list-disc space-y-2 pl-5 text-sm text-text-secondary">
            <li>
              <span className="font-medium text-text-primary">In-app</span> — delivered to the
              notification centre and top-bar bell.
            </li>
            <li>
              <span className="font-medium text-text-primary">Email / Slack / Teams</span> — not
              configured for the MSc MVP.
            </li>
            <li>
              Mark-as-read and delete are available on the{" "}
              <a href="/notifications" className="text-primary hover:underline">
                Notifications
              </a>{" "}
              page.
            </li>
          </ul>
          <p className="mt-4 flex items-center gap-2 text-xs text-text-muted">
            <Bell className="h-3.5 w-3.5" /> Preference toggles will appear here when a preferences API
            ships.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
