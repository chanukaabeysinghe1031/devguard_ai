import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { AuthTransitionLoader } from "../../components/loading";
import type { LoaderStep } from "../../components/loading";
import { useAuth } from "../../hooks/useAuth";
import { useMinDisplayTime } from "../../hooks/useMinDisplayTime";

interface LocationState {
  fromRegister?: boolean;
}

/**
 * Shown after successful registration + automatic login.
 * Stages reflect completed frontend operations; does not re-call register.
 */
export function CreatingWorkspacePage() {
  const { isAuthenticated, isLoadingUser, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state ?? {}) as LocationState;
  const [timedOut, setTimedOut] = useState(false);
  const minElapsed = useMinDisplayTime(true, 900);

  useEffect(() => {
    if (!state.fromRegister && !isAuthenticated) {
      navigate("/register", { replace: true });
    }
  }, [state.fromRegister, isAuthenticated, navigate]);

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

  const steps: LoaderStep[] = [
    { id: "org", label: "Creating organization", status: "done" },
    { id: "owner", label: "Assigning owner role", status: "done" },
    {
      id: "workspace",
      label: "Preparing your workspace",
      status: isLoadingUser || !user ? "active" : "done",
    },
    {
      id: "open",
      label: "Opening dashboard",
      status: ready ? "done" : user ? "active" : "pending",
    },
  ];

  return (
    <AuthTransitionLoader
      title="Creating your workspace"
      subtitle="Setting up your organization and administrator account"
      steps={steps}
      error={
        failed
          ? isAuthenticated
            ? "Workspace created, but loading your session stalled. Open the dashboard to continue."
            : "Workspace setup did not finish. Sign in with the account you just created."
          : null
      }
      onRetry={
        failed
          ? () => {
              if (isAuthenticated) {
                navigate("/dashboard", { replace: true });
              } else {
                navigate("/login", { replace: true });
              }
            }
          : undefined
      }
      onReturnToLogin={failed && !isAuthenticated ? () => navigate("/login", { replace: true }) : undefined}
      progress={steps.filter((s) => s.status === "done").length / steps.length}
    />
  );
}
