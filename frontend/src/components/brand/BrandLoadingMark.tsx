import { cn } from "../../utils/cn";
import { BrandMark } from "./BrandMark";
import type { BrandLogoSize } from "./BrandLogo";

export interface BrandLoadingMarkProps {
  size?: BrandLogoSize;
  className?: string;
  /** Show rotating gradient ring around the symbol. */
  showRing?: boolean;
  label?: string;
}

/** Animated symbol used inside full-screen and inline brand loaders. */
export function BrandLoadingMark({
  size = "lg",
  className,
  showRing = true,
  label = "Loading",
}: BrandLoadingMarkProps) {
  return (
    <div
      className={cn("relative inline-flex items-center justify-center", className)}
      role="status"
      aria-label={label}
    >
      {showRing && (
        <>
          <span className="brand-glow-pulse absolute inset-[-18%] rounded-full bg-primary/20 blur-xl" aria-hidden />
          <span className="brand-orbit-ring absolute inset-[-12%] rounded-full" aria-hidden />
          <span className="brand-orbit-dot absolute left-1/2 top-0 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-info" aria-hidden />
        </>
      )}
      <BrandMark size={size} framed animated={false} />
      <span className="sr-only">{label}</span>
    </div>
  );
}
