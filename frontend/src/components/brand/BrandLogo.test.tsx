import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BRAND_ALT_FULL, BRAND_ALT_ICON, brandLogoFull, brandLogoIcon } from "../../assets";
import { BrandLogo } from "./BrandLogo";
import { FullScreenBrandLoader } from "../loading/FullScreenBrandLoader";

describe("BrandLogo", () => {
  it("renders the full wordmark asset with accessible alt text", () => {
    render(<BrandLogo variant="full" size="md" priority />);
    const img = screen.getByAltText(BRAND_ALT_FULL);
    expect(img.getAttribute("src")).toBe(brandLogoFull);
    expect(img.getAttribute("loading")).toBe("eager");
    expect(img.className).toContain("object-contain");
  });

  it("renders the symbol-only asset for icon variant", () => {
    render(<BrandLogo variant="icon" size="sm" />);
    const img = screen.getByAltText(BRAND_ALT_ICON);
    expect(img.getAttribute("src")).toBe(brandLogoIcon);
    expect(img.getAttribute("loading")).toBe("lazy");
  });
});

describe("FullScreenBrandLoader", () => {
  it("renders title, stages, and retry action on error", async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();

    render(
      <FullScreenBrandLoader
        title="Signing you in"
        subtitle="Preparing your DevGuard AI workspace"
        steps={[
          { id: "a", label: "Verifying your account", status: "done" },
          { id: "b", label: "Loading organization context", status: "error" },
        ]}
        error="Sign-in failed"
        onRetry={onRetry}
      />,
    );

    expect(screen.getByRole("heading", { name: "Signing you in" })).toBeTruthy();
    expect(screen.getByText("Verifying your account")).toBeTruthy();
    expect(screen.getAllByText("Sign-in failed").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
