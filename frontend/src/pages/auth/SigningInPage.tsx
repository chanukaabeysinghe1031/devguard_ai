import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { AuthTransitionLoader } from "../../components/loading";
import type { LoaderStep } from "../../components/loading";
import { useAuth } from "../../hooks/useAuth";
import { useMinDisplayTime } from "../../hooks/useMinDisplayTime";

/**
 * Post-login transition. Starts only after credentials succeed; waits for
 * session bootstrap (`/auth/me`) with a short minimum display to avoid flash.
 */
export function SigningInPage() {
  const { isAuthenticated, isLoadingUser, user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [timedOut, setTimedOut] = useState(false);
  const minElapsed = useMinDisplayTime(true, 750);

  const next = useMemo(() => {
    const raw = searchParams.get("next");
    return raw && raw.startsWith("/") ? raw : "/dashboard";
  }, [searchParams]);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate(`/login?next=${encodeURIComponent(next)}`, { replace: true });
    }
  }, [isAuthenticated, navigate, next]);

  useEffect(() => {
    const timer = window.setTimeout(() => setTimedOut(true), 20_000);
    return () => window.clearTimeout(timer);
  }, []);

  const ready = isAuthenticated && !isLoadingUser && Boolean(user) && minElapsed;

  useEffect(() => {
    if (ready) {
      navigate(next, { replace: true });
    }
  }, [ready, navigate, next]);

  const failed = timedOut && !ready;

  const steps: LoaderStep[] = [
    {
      id: "verify",
      label: "Verifying your account",
      status: isAuthenticated ? "done" : "active",
    },
    {
      id: "org",
      label: "Loading organization context",
      status: !isAuthenticated ? "pending" : isLoadingUser ? "active" : user ? "done" : "active",
    },
    {
      id: "dashboard",
      label: "Preparing your dashboard",
      status: ready ? "done" : user && minElapsed ? "active" : "pending",
    },
  ];

  return (
    <AuthTransitionLoader
      title="Signing you in"
      subtitle="Preparing your DevGuard AI workspace"
      steps={steps}
      error={failed ? "Sign-in is taking longer than expected. Please try again." : null}
      onRetry={
        failed
          ? () => {
              setTimedOut(false);
              window.location.assign(`/auth/signing-in?next=${encodeURIComponent(next)}`);
            }
          : undefined
      }
      onReturnToLogin={failed ? () => navigate("/login", { replace: true }) : undefined}
      progress={steps.filter((s) => s.status === "done").length / steps.length}
    />
  );
}
