import { BrandLoadingMark } from "../brand/BrandLoadingMark";
import { cn } from "../../utils/cn";

export function InlineBrandSpinner({
  label = "Loading",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-3 py-10", className)}>
      <BrandLoadingMark size="md" label={label} />
      <p className="text-sm text-text-secondary">{label}</p>
    </div>
  );
}
