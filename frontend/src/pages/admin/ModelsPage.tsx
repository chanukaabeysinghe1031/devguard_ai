import { FlaskConical } from "lucide-react";

import { EmptyState } from "../../components/ui/EmptyState";
import { PageHeader } from "../../components/ui/PageHeader";

export function ModelsPage() {
  return (
    <div>
      <PageHeader title="Models" description="Classifier and model version management." />
      <EmptyState
        icon={FlaskConical}
        title="Model management coming soon"
        description="Model version activation and comparison tooling will be available once the model registry API is implemented."
      />
    </div>
  );
}
