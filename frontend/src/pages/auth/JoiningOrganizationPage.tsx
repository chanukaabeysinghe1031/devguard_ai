import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { AuthTransitionLoader } from "../../components/loading";
import type { LoaderStep } from "../../components/loading";
import { useAuth } from "../../hooks/useAuth";
import { useMinDisplayTime } from "../../hooks/useMinDisplayTime";

export function JoiningOrganizationPage() {
  const { isAuthenticated, isLoadingUser, user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const organizationName = searchParams.get("org") ?? undefined;
  const [timedOut, setTimedOut] = useState(false);
  const minElapsed = useMinDisplayTime(true, 800);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate("/login", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    const timer = window.setTimeout(() => setTimedOut(true), 20_000);
    return () => window.clearTimeout(timer);
  }, []);

  const ready = isAuthenticated && !isLoadingUser && Boolean(user) && minElapsed;

  useEffect(() => {
    if (ready) {
      navigate("/dashboard", { replace: true });
    }
  }, [ready, navigate]);

  const failed = timedOut && !ready;
  const orgLabel = organizationName ? ` (${organizationName})` : "";

  const steps: LoaderStep[] = [
    { id: "join", label: "Joining your organization", status: "done" },
    { id: "confirm", label: "Confirming your membership", status: user ? "done" : "active" },
    {
      id: "workspace",
      label: "Preparing your workspace",
      status: ready ? "done" : user ? "active" : "pending",
    },
  ];

  return (
    <AuthTransitionLoader
      title="Joining your organization"
      subtitle={`Confirming your membership${orgLabel}`}
      steps={steps}
      error={failed ? "Could not finish joining. Open the dashboard or sign in again." : null}
      onRetry={failed ? () => navigate("/dashboard", { replace: true }) : undefined}
      onReturnToLogin={failed ? () => navigate("/login", { replace: true }) : undefined}
      progress={steps.filter((s) => s.status === "done").length / steps.length}
    />
  );
}
