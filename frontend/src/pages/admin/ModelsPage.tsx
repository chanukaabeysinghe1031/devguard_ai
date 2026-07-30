import { FlaskConical } from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState } from "../../components/ui/EmptyState";
import { PageHeader } from "../../components/ui/PageHeader";

export function ModelsPage() {
  return (
    <div>
      <PageHeader
        title="AI Models"
        description="Model registry and provider configuration for this organisation."
      />
      <EmptyState
        icon={FlaskConical}
        title="Deferred — not in MSc MVP"
        description="A product model-registry API is not implemented. Runtime providers remain server-configured via environment flags. No model switching actions are available here."
        action={
          <Link to="/admin/system-health" className="text-sm font-medium text-primary hover:underline">
            View system health
          </Link>
        }
      />
    </div>
  );
}
