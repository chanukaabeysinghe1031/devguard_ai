import { Button } from "../ui/Button";
import { BrandLoadingMark } from "../brand/BrandLoadingMark";
import { BrandLogo } from "../brand/BrandLogo";
import { cn } from "../../utils/cn";

export interface LoaderStep {
  id: string;
  label: string;
  status: "pending" | "active" | "done" | "error";
}

export interface FullScreenBrandLoaderProps {
  title: string;
  subtitle?: string;
  steps?: LoaderStep[];
  projectName?: string;
  showWordmark?: boolean;
  error?: string | null;
  onRetry?: () => void;
  secondaryAction?: { label: string; onClick: () => void };
  className?: string;
  /** Determinate 0–1 when known; omit for indeterminate bar. */
  progress?: number | null;
}

export function FullScreenBrandLoader({
  title,
  subtitle,
  steps,
  projectName,
  showWordmark = false,
  error,
  onRetry,
  secondaryAction,
  className,
  progress = null,
}: FullScreenBrandLoaderProps) {
  const liveStatus =
    error ??
    steps?.find((s) => s.status === "active")?.label ??
    steps?.find((s) => s.status === "done")?.label ??
    title;

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex w-full flex-col items-center justify-center bg-background px-6 py-10",
        className,
      )}
      role="status"
      aria-live="polite"
      aria-busy={!error}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-50"
        style={{
          backgroundImage:
            "radial-gradient(circle at 50% 30%, rgba(37,99,235,0.22), transparent 42%), radial-gradient(circle at 70% 70%, rgba(124,58,237,0.16), transparent 40%)",
        }}
        aria-hidden
      />

      <div className="relative z-10 flex w-full max-w-md flex-col items-center text-center">
        {showWordmark && (
          <div className="mb-8">
            <BrandLogo variant="full" size="md" priority animated />
          </div>
        )}

        <BrandLoadingMark size="xl" label={title} />

        {projectName && (
          <p className="mt-6 text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
            {projectName}
          </p>
        )}

        <h1 className="mt-4 text-2xl font-bold text-text-primary">{title}</h1>
        {subtitle && <p className="mt-2 text-sm text-text-secondary">{subtitle}</p>}

        <p className="sr-only">{liveStatus}</p>

        {!error && (
          <div className="mt-8 h-1 w-full max-w-xs overflow-hidden rounded-full bg-surface-interactive">
            {typeof progress === "number" ? (
              <div
                className="h-full rounded-full bg-gradient-to-r from-info via-primary to-secondary transition-[width] duration-300"
                style={{ width: `${Math.max(4, Math.min(100, progress * 100))}%` }}
              />
            ) : (
              <div className="brand-progress-indeterminate h-full w-full" />
            )}
          </div>
        )}

        {steps && steps.length > 0 && (
          <ol className="mt-8 w-full space-y-2 text-left">
            {steps.map((step) => (
              <li
                key={step.id}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm",
                  step.status === "active" && "bg-primary/10 text-text-primary",
                  step.status === "done" && "text-text-secondary",
                  step.status === "pending" && "text-text-muted",
                  step.status === "error" && "bg-danger/10 text-danger",
                )}
              >
                <span
                  className={cn(
                    "h-2 w-2 shrink-0 rounded-full",
                    step.status === "done" && "bg-success",
                    step.status === "active" && "bg-primary brand-glow-pulse",
                    step.status === "pending" && "bg-text-disabled",
                    step.status === "error" && "bg-danger",
                  )}
                  aria-hidden
                />
                {step.label}
              </li>
            ))}
          </ol>
        )}

        {error && (
          <div className="mt-8 w-full rounded-lg border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}

        {(onRetry || secondaryAction) && (
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            {onRetry && (
              <Button type="button" onClick={onRetry}>
                Retry
              </Button>
            )}
            {secondaryAction && (
              <Button type="button" variant="outline" onClick={secondaryAction.onClick}>
                {secondaryAction.label}
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
