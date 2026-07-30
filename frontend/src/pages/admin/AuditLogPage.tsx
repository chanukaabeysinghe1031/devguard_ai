import { ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState } from "../../components/ui/EmptyState";
import { PageHeader } from "../../components/ui/PageHeader";

export function AuditLogPage() {
  return (
    <div>
      <PageHeader
        title="Audit Log"
        description="Organisation security and administration events."
      />
      <EmptyState
        icon={ShieldCheck}
        title="Deferred — not in MSc MVP"
        description="The audit_logs table exists, but list APIs and mutation writers are not part of the MSc product surface. No export or filter actions are offered here."
        action={
          <Link to="/admin/users" className="text-sm font-medium text-primary hover:underline">
            Manage organisation users
          </Link>
        }
      />
    </div>
  );
}
