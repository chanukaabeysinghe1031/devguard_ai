import { BarChart3 } from "lucide-react";

import { EmptyState } from "../../components/ui/EmptyState";
import { PageHeader } from "../../components/ui/PageHeader";

export function AdminEvaluationPage() {
  return (
    <div>
      <PageHeader title="Evaluation administration" description="Manage evaluation runs and research datasets." />
      <EmptyState
        icon={BarChart3}
        title="Evaluation administration coming soon"
        description="Admin controls for triggering and reviewing evaluation runs will be available once Module 14 is implemented."
      />
    </div>
  );
}
