import { cn } from "../../utils/cn";
import { BrandLogo, type BrandLogoSize } from "./BrandLogo";

export interface BrandMarkProps {
  size?: BrandLogoSize;
  className?: string;
  /** Soft rounded frame — helps when the PNG has a fixed dark plate. */
  framed?: boolean;
  priority?: boolean;
  animated?: boolean;
  /** Accessible label when used as a decorative brand chip. */
  title?: string;
}

/** Symbol-only brand mark for compact chrome (sidebar, mobile, overlays). */
export function BrandMark({
  size = "sm",
  className,
  framed = false,
  priority = false,
  animated = false,
  title = "DevGuard AI",
}: BrandMarkProps) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex shrink-0 items-center justify-center overflow-hidden",
        framed && "rounded-lg bg-black/40 ring-1 ring-white/10 shadow-[0_0_20px_rgba(37,99,235,0.25)]",
        className,
      )}
    >
      <BrandLogo variant="icon" size={size} priority={priority} animated={animated} />
    </span>
  );
}
