import { BarChart3 } from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState } from "../../components/ui/EmptyState";
import { PageHeader } from "../../components/ui/PageHeader";

export function AdminEvaluationPage() {
  return (
    <div>
      <PageHeader
        title="Evaluation administration"
        description="Administrative controls for research evaluation runs."
      />
      <EmptyState
        icon={BarChart3}
        title="Deferred — not in MSc MVP"
        description="Admin evaluation controls (start/stop experiments, mutate gold labels) are intentionally out of scope. Research metrics are available as a read-only view."
        action={
          <Link to="/evaluation" className="text-sm font-medium text-primary hover:underline">
            Open research evaluation metrics
          </Link>
        }
      />
    </div>
  );
}
