import type { LucideIcon } from "lucide-react";

import { cn } from "../../utils/cn";
import { Skeleton } from "./Skeleton";

export function MetricCard({
  label,
  value,
  icon: Icon,
  tone = "primary",
  isLoading = false,
  hint,
}: {
  label: string;
  value: string;
  icon: LucideIcon;
  tone?: "primary" | "success" | "warning" | "danger" | "info" | "secondary";
  isLoading?: boolean;
  hint?: string;
}) {
  const toneClasses: Record<typeof tone, string> = {
    primary: "bg-primary/15 text-primary",
    success: "bg-success/15 text-success",
    warning: "bg-warning/15 text-warning",
    danger: "bg-danger/15 text-danger",
    info: "bg-info/15 text-info",
    secondary: "bg-secondary/15 text-secondary",
  };

  return (
    <div className="rounded-lg border border-border bg-surface-elevated p-5 shadow-card">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-text-muted">{label}</p>
        <span className={cn("flex h-9 w-9 items-center justify-center rounded-md", toneClasses[tone])}>
          <Icon className="h-4.5 w-4.5" />
        </span>
      </div>
      {isLoading ? (
        <Skeleton className="mt-3 h-8 w-20" />
      ) : (
        <p className="mt-2 text-[28px] font-bold leading-none text-text-primary">{value}</p>
      )}
      {hint && <p className="mt-1.5 text-xs text-text-muted">{hint}</p>}
    </div>
  );
}
