import { expect, test } from "@playwright/test";

import { registerViaUi, skipBrandSplash, uniqueUser } from "./helpers/auth";
import { createProjectViaUi } from "./helpers/project";

test.describe("Phase 5D branding and transitions", () => {
  test("welcome splash animates logo then text before register", async ({ page }) => {
    await page.goto("/welcome?next=/register");
    await expect(page.getByAltText("DevGuard AI")).toBeVisible();
    await expect(page.getByRole("heading", { name: /DevGuard/i })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("AI-Powered Incident Intelligence", { exact: true })).toBeVisible({
      timeout: 6_000,
    });
    await page.waitForURL("**/register", { timeout: 12_000 });
    await expect(page.getByRole("heading", { name: /Create your DevGuard AI workspace/i })).toBeVisible();
  });

  test("opening login without splash pass redirects through welcome", async ({ page }) => {
    await page.goto("/login");
    await expect(page).toHaveURL(/\/welcome/);
    await expect(page.getByAltText("DevGuard AI")).toBeVisible();
    await page.waitForURL("**/login", { timeout: 12_000 });
    await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  });

  test("login and register show brand mark; sign-in shows transition", async ({ page }) => {
    await skipBrandSplash(page);
    await page.goto("/login");
    await expect(page.getByAltText("DevGuard AI")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();

    await page.goto("/register");
    await expect(page.getByAltText("DevGuard AI")).toBeVisible();

    const user = uniqueUser("brand-login");
    await registerViaUi(page, user);
    await logoutViaUiSafe(page);

    await skipBrandSplash(page);
    await page.goto("/login");
    await page.getByLabel(/Email/).fill(user.email);
    await page.getByLabel(/^Password/).fill(user.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(
      page.getByRole("heading", { name: "Signing you in" }).or(page.getByRole("heading", { name: /Dashboard/i })),
    ).toBeVisible({ timeout: 20_000 });
    await page.waitForURL("**/dashboard", { timeout: 45_000 });
  });

  test("register shows workspace creation transition", async ({ page }) => {
    await skipBrandSplash(page);
    const user = uniqueUser("brand-register");
    await page.goto("/register");
    await page.getByLabel(/^Organization name/).fill(user.organizationName!);
    await page.getByLabel(/^Your name/).fill(user.fullName);
    await page.getByLabel(/Work email|Email/).fill(user.email);
    await page.getByLabel(/^Password/).fill(user.password);
    await page.getByLabel(/^Confirm password/).fill(user.password);
    await page.getByRole("button", { name: /Create workspace/i }).click();
    await expect(page.getByRole("heading", { name: "Creating your workspace" })).toBeVisible({
      timeout: 30_000,
    });
    await page.waitForURL("**/dashboard", { timeout: 45_000 });
  });

  test("sidebar uses symbol mark; opening a project shows bootstrap loader", async ({ page }) => {
    test.setTimeout(90_000);
    const user = uniqueUser("brand-project");
    await registerViaUi(page, user);

    const sidebar = page.locator("aside[aria-label='Primary navigation']");
    await expect(sidebar.getByAltText("DevGuard AI")).toBeVisible();
    await expect(sidebar.getByText("DevGuard AI")).toBeVisible();

    const stamp = Date.now().toString(36);
    const projectName = `Brand Project ${stamp}`;
    await createProjectViaUi(page, projectName, `BRAND${stamp}`.toUpperCase().slice(0, 12));
    const projectUrl = page.url();
    await expect(page.getByRole("heading", { name: projectName })).toBeVisible({ timeout: 30_000 });

    await page.goto("/dashboard");
    await page.goto(projectUrl);
    const loader = page.getByRole("heading", { name: "Loading project" });
    const projectHeading = page.getByRole("heading", { name: projectName });
    await expect(loader.or(projectHeading)).toBeVisible({ timeout: 20_000 });
    await expect(projectHeading).toBeVisible({ timeout: 45_000 });
  });

  test("mobile login layout has no horizontal overflow", async ({ page }) => {
    await skipBrandSplash(page);
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/login");
    const overflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth + 1;
    });
    expect(overflow).toBe(false);
  });
});

async function logoutViaUiSafe(page: import("@playwright/test").Page): Promise<void> {
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await page.waitForURL("**/login", { timeout: 15_000 });
}
