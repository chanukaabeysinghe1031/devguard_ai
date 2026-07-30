import { FileQuestion } from "lucide-react";

import { EmptyState } from "../../components/ui/EmptyState";
import { LinkButton } from "../../components/ui/LinkButton";

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <EmptyState
        icon={FileQuestion}
        title="Page not found"
        description="The page you're looking for doesn't exist or may have been moved."
        action={<LinkButton to="/dashboard">Back to dashboard</LinkButton>}
      />
    </div>
  );
}
