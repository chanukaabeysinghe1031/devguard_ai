import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";

import { cn } from "../../utils/cn";

export type AlertVariant = "info" | "success" | "warning" | "danger";

const VARIANT_CONFIG: Record<AlertVariant, { icon: typeof Info; className: string }> = {
  info: { icon: Info, className: "border-info/30 bg-info/10 text-info" },
  success: { icon: CheckCircle2, className: "border-success/30 bg-success/10 text-success" },
  warning: { icon: AlertTriangle, className: "border-warning/30 bg-warning/10 text-warning" },
  danger: { icon: XCircle, className: "border-danger/30 bg-danger/10 text-danger" },
};

export function Alert({
  variant = "info",
  title,
  children,
  action,
  className,
}: {
  variant?: AlertVariant;
  title?: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  const { icon: Icon, className: variantClass } = VARIANT_CONFIG[variant];
  return (
    <div
      role="alert"
      className={cn("flex items-start gap-3 rounded-md border px-4 py-3 text-sm", variantClass, className)}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1 text-text-primary">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className="mt-0.5 text-text-secondary">{children}</div>}
      </div>
      {action}
    </div>
  );
}

export function ErrorRetryAlert({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <Alert
      variant="danger"
      title="Something went wrong"
      action={
        onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md border border-danger/40 px-3 py-1.5 text-xs font-medium text-danger transition-colors hover:bg-danger/10"
          >
            Retry
          </button>
        ) : undefined
      }
    >
      {message}
    </Alert>
  );
}
