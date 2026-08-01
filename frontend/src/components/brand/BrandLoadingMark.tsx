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
      className={cn(
        // Padding reserves layout space for the absolute orbit/glow so title text
        // cannot sit on top of the scaled visual ring.
        "relative inline-flex items-center justify-center p-7 sm:p-8",
        className,
      )}
      role="status"
      aria-label={label}
    >
      {showRing && (
        <>
          <span
            className="brand-glow-pulse pointer-events-none absolute inset-2 rounded-full bg-primary/20 blur-xl"
            aria-hidden
          />
          <span className="brand-orbit-ring pointer-events-none absolute inset-3 rounded-full" aria-hidden />
          <span
            className="brand-orbit-dot pointer-events-none absolute left-1/2 top-3 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-info"
            aria-hidden
          />
        </>
      )}
      <BrandMark size={size} framed={false} animated={false} className="relative z-10" />
      <span className="sr-only">{label}</span>
    </div>
  );
}
