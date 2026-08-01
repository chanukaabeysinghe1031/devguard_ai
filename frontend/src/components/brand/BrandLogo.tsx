import { cn } from "../../utils/cn";
import { BRAND_ALT_FULL, BRAND_ALT_ICON, brandLogoFull, brandLogoIcon } from "../../assets";

export type BrandLogoVariant = "full" | "icon";
export type BrandLogoSize = "xs" | "sm" | "md" | "lg" | "xl";

const ICON_SIZE: Record<BrandLogoSize, string> = {
  xs: "h-8 w-8",
  sm: "h-10 w-10",
  md: "h-14 w-14",
  lg: "h-20 w-20",
  xl: "h-40 w-40",
};

const FULL_WIDTH: Record<BrandLogoSize, string> = {
  xs: "w-[140px]",
  sm: "w-[180px]",
  md: "w-[240px]",
  lg: "w-[320px]",
  xl: "w-[400px]",
};

export interface BrandLogoProps {
  variant?: BrandLogoVariant;
  size?: BrandLogoSize;
  className?: string;
  /** Prefer eager load for above-the-fold auth branding. */
  priority?: boolean;
  animated?: boolean;
}

/**
 * Reusable DevGuard AI brand image.
 * - `full` → complete wordmark (auth / onboarding headers)
 * - `icon` → symbol-only (sidebar, loaders, compact chrome)
 */
export function BrandLogo({
  variant = "full",
  size = "md",
  className,
  priority = false,
  animated = false,
}: BrandLogoProps) {
  const isIcon = variant === "icon";
  const src = isIcon ? brandLogoIcon : brandLogoFull;
  const alt = isIcon ? BRAND_ALT_ICON : BRAND_ALT_FULL;

  return (
    <img
      src={src}
      alt={alt}
      loading={priority ? "eager" : "lazy"}
      decoding="async"
      draggable={false}
      className={cn(
        "object-contain select-none",
        isIcon ? ICON_SIZE[size] : cn(FULL_WIDTH[size], "h-auto max-w-full"),
        animated && "brand-logo-enter",
        className,
      )}
    />
  );
}
