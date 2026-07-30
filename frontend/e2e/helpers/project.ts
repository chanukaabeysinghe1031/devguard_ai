import type { Page } from "@playwright/test";

/**
 * Clicks a submit button that (a) disables itself via `isLoading` the instant its mutation
 * starts and (b) navigates away as soon as that mutation resolves.
 *
 * That combination is a known Playwright footgun: the physical click is delivered and the
 * mutation does fire, but by the time Playwright's `.click()` runs its post-action stability
 * re-check, the button has already gone `disabled` and then been removed from the DOM by the
 * navigation. Playwright treats that as "the action needs retrying", retries against a page that
 * no longer has a matching button, and only gives up with a `TimeoutError` once its action
 * timeout elapses — even though the click's real-world effect (the navigation) already
 * succeeded. We give the click a short timeout, ignore a timeout error from it specifically
 * (any other rejection still propagates), and treat `waitForURL` — a direct observation of the
 * real success signal — as the actual assertion.
 */
async function submitAndWaitForUrl(page: Page, buttonName: string, urlPattern: RegExp, timeout = 20_000): Promise<void> {
  const button = page.getByRole("button", { name: buttonName, exact: true });
  await Promise.all([
    page.waitForURL(urlPattern, { timeout }),
    button.click({ timeout: 5_000 }).catch(() => undefined),
  ]);
}

/**
 * Creates a project through the 3-step wizard, accepting the default CI/cloud/environment
 * values on steps 2 and 3.
 */
export async function createProjectViaUi(page: Page, name: string, key: string): Promise<void> {
  await page.goto("/projects/new");
  await page.getByLabel("Project name").fill(name);
  await page.getByLabel("Project key").fill(key);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await submitAndWaitForUrl(page, "Create project", /\/projects\/[0-9a-f-]+$/);
}

export { submitAndWaitForUrl };
