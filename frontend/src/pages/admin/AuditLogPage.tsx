import { ShieldCheck } from "lucide-react";

import { EmptyState } from "../../components/ui/EmptyState";
import { PageHeader } from "../../components/ui/PageHeader";

export function AuditLogPage() {
  return (
    <div>
      <PageHeader title="Audit log" description="Security and administrative activity log." />
      <EmptyState
        icon={ShieldCheck}
        title="Audit log coming soon"
        description="A full audit trail of authentication, role changes, and administrative actions will be available in a future module."
      />
    </div>
  );
}
