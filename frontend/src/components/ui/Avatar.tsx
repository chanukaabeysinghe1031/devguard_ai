import { cn } from "../../utils/cn";
import { initialsFromName } from "../../utils/formatters";

const SIZE_CLASSES: Record<"sm" | "md" | "lg", string> = {
  sm: "h-7 w-7 text-xs",
  md: "h-9 w-9 text-sm",
  lg: "h-12 w-12 text-base",
};

export function Avatar({
  name,
  src,
  size = "md",
  className,
}: {
  name?: string | null;
  src?: string | null;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  if (src) {
    return (
      <img
        src={src}
        alt={name ?? "User avatar"}
        className={cn("rounded-full object-cover", SIZE_CLASSES[size], className)}
      />
    );
  }
  return (
    <div
      className={cn(
        "flex items-center justify-center rounded-full bg-primary/20 font-semibold text-primary",
        SIZE_CLASSES[size],
        className,
      )}
      aria-hidden="true"
    >
      {initialsFromName(name)}
    </div>
  );
}
