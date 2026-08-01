import { useEffect, useMemo, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { BRAND_NAME, BRAND_TAGLINE, brandLogoIcon } from "../../assets";
import { useAuth } from "../../hooks/useAuth";
import { usePrefersReducedMotion } from "../../hooks/usePrefersReducedMotion";
import { cn } from "../../utils/cn";

type SplashPhase = "logo" | "title" | "tagline" | "exit";

/** Total sequence ≈ 5 seconds. */
const PHASE_MS = {
  logo: 1400,
  title: 1400,
  tagline: 1400,
  exit: 800,
} as const;

/**
 * Full-screen brand intro before login/register.
 * Sequence: symbol → “DevGuard AI” → tagline → navigate with fromSplash state.
 */
export function BrandSplashPage() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const reducedMotion = usePrefersReducedMotion();
  const [phase, setPhase] = useState<SplashPhase>("logo");

  const next = useMemo(() => {
    const raw = searchParams.get("next");
    if (raw && raw.startsWith("/") && !raw.startsWith("//")) return raw;
    return "/login";
  }, [searchParams]);

  useEffect(() => {
    if (isAuthenticated) return;

    const goNext = () => {
      navigate(next, { replace: true, state: { fromSplash: true } });
    };

    if (reducedMotion) {
      const timer = window.setTimeout(goNext, 500);
      return () => window.clearTimeout(timer);
    }

    const timers: number[] = [];
    let elapsed = 0;
    const schedule = (nextPhase: SplashPhase, delay: number) => {
      elapsed += delay;
      timers.push(window.setTimeout(() => setPhase(nextPhase), elapsed));
    };

    schedule("title", PHASE_MS.logo);
    schedule("tagline", PHASE_MS.title);
    schedule("exit", PHASE_MS.tagline);
    timers.push(
      window.setTimeout(goNext, PHASE_MS.logo + PHASE_MS.title + PHASE_MS.tagline + PHASE_MS.exit),
    );

    return () => timers.forEach((id) => window.clearTimeout(id));
  }, [isAuthenticated, navigate, next, reducedMotion]);

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const showTitle = phase === "title" || phase === "tagline" || phase === "exit";
  const showTagline = phase === "tagline" || phase === "exit";

  return (
    <div
      className={cn(
        "fixed inset-0 z-[100] flex flex-col items-center justify-center overflow-hidden bg-background px-6",
        phase === "exit" && "brand-splash-exit",
      )}
      role="status"
      aria-live="polite"
      aria-label="DevGuard AI loading"
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-70"
        style={{
          backgroundImage:
            "radial-gradient(circle at 50% 40%, rgba(37,99,235,0.32), transparent 42%), radial-gradient(circle at 70% 70%, rgba(124,58,237,0.22), transparent 40%)",
        }}
        aria-hidden
      />

      <div className="relative z-10 flex max-w-lg flex-col items-center text-center">
        <img
          src={brandLogoIcon}
          alt="DevGuard AI"
          loading="eager"
          decoding="async"
          draggable={false}
          className={cn(
            "h-52 w-52 object-contain drop-shadow-[0_0_28px_rgba(37,99,235,0.35)] sm:h-64 sm:w-64",
            "brand-splash-logo",
            phase !== "logo" && "brand-float",
          )}
        />

        <h1
          className={cn(
            "mt-10 text-4xl font-bold tracking-tight text-text-primary sm:text-5xl",
            showTitle ? "brand-splash-text-in" : "pointer-events-none absolute opacity-0",
          )}
        >
          <span>DevGuard </span>
          <span className="bg-gradient-to-r from-info via-primary to-secondary bg-clip-text text-transparent">
            AI
          </span>
        </h1>

        <p
          className={cn(
            "mt-5 text-sm font-semibold uppercase tracking-[0.22em] text-text-secondary",
            showTagline ? "brand-splash-text-in" : "pointer-events-none absolute opacity-0",
          )}
        >
          {BRAND_TAGLINE}
        </p>

        <p className="sr-only">
          {showTagline
            ? `${BRAND_NAME} — ${BRAND_TAGLINE}`
            : showTitle
              ? BRAND_NAME
              : "Loading DevGuard AI"}
        </p>
      </div>
    </div>
  );
}
