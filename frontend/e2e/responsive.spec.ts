import { expect, test } from "@playwright/test";

import { registerViaUi, uniqueUser } from "./helpers/auth";
import { sidebarNav } from "./helpers/nav";

/**
 * Responsive layout smoke test across mobile / tablet / desktop breakpoints.
 * The Tailwind breakpoint driving the sidebar/mobile-nav switch is `lg` (1024px), so:
 * - 375px and 768px: the desktop `<aside>` sidebar is present but CSS-hidden; the hamburger
 *   "Open navigation" button in the top bar is visible instead.
 * - 1440px: the desktop sidebar is visible and the hamburger button is hidden.
 */

const VIEWPORTS: Array<{ name: string; width: number; height: number; expectMobileMenu: boolean }> = [
  { name: "mobile (375px)", width: 375, height: 812, expectMobileMenu: true },
  { name: "tablet (768px)", width: 768, height: 1024, expectMobileMenu: true },
  { name: "desktop (1440px)", width: 1440, height: 900, expectMobileMenu: false },
];

for (const viewport of VIEWPORTS) {
  test.describe(`responsive layout — ${viewport.name}`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test("login page renders", async ({ page }) => {
      await page.goto("/login");
      await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
      await expect(page.getByLabel("Email")).toBeVisible();
      await expect(page.getByLabel(/^Password/)).toBeVisible();
    });

    test("dashboard shell renders with the expected navigation affordance", async ({ page }) => {
      const user = uniqueUser(`resp-${viewport.width}`);
      await registerViaUi(page, user);
      await expect(page).toHaveURL(/\/dashboard$/);

      const mobileMenuButton = page.getByRole("button", { name: "Open navigation" });
      const sidebar = sidebarNav(page);

      if (viewport.expectMobileMenu) {
        await expect(mobileMenuButton).toBeVisible();
        await expect(sidebar).toBeHidden();

        // Opening the drawer is the meaningful behavioural check; we deliberately avoid asserting
        // on nav *link* text here, since the (CSS-hidden) desktop sidebar's identical links remain
        // in the DOM and would make role/name locators ambiguous once the drawer is also open.
        await mobileMenuButton.click();
        await expect(page.getByRole("button", { name: "Close navigation" })).toBeVisible();
      } else {
        await expect(sidebar).toBeVisible();
        await expect(mobileMenuButton).toBeHidden();
        await expect(sidebar.getByText("DevGuard AI")).toBeVisible();
      }
    });
  });
}
