import { ShieldAlert } from "lucide-react";

import { EmptyState } from "../../components/ui/EmptyState";
import { LinkButton } from "../../components/ui/LinkButton";

export function ForbiddenPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <EmptyState
        icon={ShieldAlert}
        title="Access restricted"
        description="You don't have permission to view this page. Contact an organization admin if you believe this is a mistake."
        action={<LinkButton to="/dashboard">Back to dashboard</LinkButton>}
      />
    </div>
  );
}
