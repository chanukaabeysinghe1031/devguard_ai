import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { SPLASH_SEEN_KEY } from "../assets";
import { useAuth } from "../hooks/useAuth";

/**
 * Guests must pass through `/welcome` before auth forms.
 * After the splash finishes it navigates with `state.fromSplash`.
 * E2E can set `sessionStorage[SPLASH_SEEN_KEY]` to skip.
 */
export function RequireBrandSplash({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (isAuthenticated) {
    return <>{children}</>;
  }

  const fromSplash = Boolean(
    (location.state as { fromSplash?: boolean } | null)?.fromSplash,
  );
  const e2eSkip = sessionStorage.getItem(SPLASH_SEEN_KEY) === "1";

  if (fromSplash || e2eSkip) {
    return <>{children}</>;
  }

  const next = encodeURIComponent(location.pathname + location.search);
  return <Navigate to={`/welcome?next=${next}`} replace />;
}
