import type { Page } from "@playwright/test";

/**
 * Locator for the desktop sidebar landmark (visible at the `lg` breakpoint and above).
 * Rendered as `<aside aria-label="Primary navigation">`, which maps to the ARIA
 * "complementary" role (NOT "navigation" — that implicit mapping only applies to `<nav>`).
 */
export function sidebarNav(page: Page) {
  return page.getByRole("complementary", { name: "Primary navigation" });
}

/** Clicks a primary nav link scoped to the desktop sidebar (avoids ambiguity with the mobile nav). */
export async function clickSidebarLink(page: Page, label: string): Promise<void> {
  await sidebarNav(page).getByRole("link", { name: label, exact: true }).click();
}

/** Opens the mobile navigation drawer via the top bar hamburger button (visible below lg breakpoint). */
export async function openMobileNav(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Open navigation" }).click();
}

/** Closes the mobile navigation drawer. */
export async function closeMobileNav(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Close navigation" }).click();
}

export async function gotoDashboard(page: Page): Promise<void> {
  await page.goto("/dashboard");
  await page.waitForURL("**/dashboard");
}
