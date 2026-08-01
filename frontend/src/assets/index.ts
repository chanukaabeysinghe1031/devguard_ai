/**
 * DevGuard AI brand assets (Phase 5D).
 *
 * Source originals (preserved):
 * - frontend/assets/logo2.png — complete stacked logo (shield + wordmark + tagline)
 * - frontend/assets/logo.png — symbol-only shield
 * - frontend/assets/banner.png — legacy wide wordmark (superseded by logo2)
 *
 * Runtime copies are alpha-cropped from the transparent sources so the shield
 * fills the frame (no large empty plate / black padding).
 */
import brandLogoFullUrl from "./brand-logo-full.png";
import brandLogoIconUrl from "./brand-logo-icon.png";

export { SPLASH_SEEN_KEY } from "./brandConstants";

export const brandLogoFull = brandLogoFullUrl;
export const brandLogoIcon = brandLogoIconUrl;

export const BRAND_ALT_FULL = "DevGuard AI — AI-Powered Incident Intelligence";
export const BRAND_ALT_ICON = "DevGuard AI";

export const BRAND_NAME = "DevGuard AI";
/** Correct product tagline (source logo2 image has a typo; UI text uses this). */
export const BRAND_TAGLINE = "AI-Powered Incident Intelligence";
