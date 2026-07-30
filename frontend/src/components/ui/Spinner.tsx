import { Loader2 } from "lucide-react";

import { cn } from "../../utils/cn";

const SIZE_CLASSES: Record<"sm" | "md" | "lg", string> = {
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-9 w-9",
};

export function Spinner({
  size = "md",
  className,
}: {
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  return (
    <Loader2
      role="status"
      aria-label="Loading"
      className={cn("animate-spin text-current", SIZE_CLASSES[size], className)}
    />
  );
}
