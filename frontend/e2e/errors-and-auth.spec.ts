import { expect, test } from "@playwright/test";

import { loginViaUi, registerViaUi, uniqueUser } from "./helpers/auth";
import { EMPTY_FILE_PATH, getOversizedFilePath, UNSUPPORTED_FILE_PATH } from "./helpers/fixtures";
import { createProjectViaUi } from "./helpers/project";

/**
 * Negative-path and auth-edge-case coverage.
 *
 * Assumptions verified against current source:
 * - `/403`, `/error`, and the catch-all 404 route are nested *inside* the `RequireAuth`-wrapped
 *   route group in `router.tsx`, so they only render their intended page when already logged in
 *   (otherwise `RequireAuth` redirects to `/login` first). Both checks below log in first.
 * - Registration always creates a brand-new organization with the registering user as
 *   `organization_owner` (see `AuthService.register` → `create_default_organization_for_user`).
 *   There is no self-serve "invite a viewer" flow reachable from the UI in this build, so a true
 *   non-admin/viewer 403 check against `/admin/models` isn't feasible without backend fixtures;
 *   per the task's own fallback, we instead assert `/403` and an unknown route render correctly.
 */

test.describe("errors and auth edge cases", () => {
  test("unsupported file type is rejected with a validation message", async ({ page }) => {
    const user = uniqueUser("err-unsupported");
    await registerViaUi(page, user);

    const stamp = Date.now().toString(36);
    const projectName = `E2E Errors Project ${stamp}`;
    await createProjectViaUi(page, projectName, `E2EERR${stamp}`.toUpperCase().slice(0, 20));

    await page.goto("/incidents/new");
    await page.getByLabel(/^Project/).selectOption({ label: projectName });
    await page.getByLabel(/^Title/).fill(`E2E Unsupported File ${stamp}`);
    await page.getByRole("button", { name: "Continue" }).click();

    await page.locator('input[type="file"]').setInputFiles(UNSUPPORTED_FILE_PATH);
    await page.getByRole("button", { name: "Upload & continue" }).click();

    // Scoped to the `Alert` component's `role="alert"` rather than a bare text match, since the
    // incident title / uploaded filename can otherwise coincidentally contain the same substring.
    // Actual copy is file-extension-specific (e.g. "Executable file types are not allowed."),
    // so match generically on "not allowed" rather than a fixed "unsupported file" phrase.
    await expect(page.getByRole("alert")).toContainText(/not allowed/i, { timeout: 15_000 });
  });

  test("empty file is rejected with a validation message", async ({ page }) => {
    const user = uniqueUser("err-empty");
    await registerViaUi(page, user);

    const stamp = Date.now().toString(36);
    const projectName = `E2E Errors Project ${stamp}`;
    await createProjectViaUi(page, projectName, `E2EERR${stamp}`.toUpperCase().slice(0, 20));

    await page.goto("/incidents/new");
    await page.getByLabel(/^Project/).selectOption({ label: projectName });
    await page.getByLabel(/^Title/).fill(`E2E Empty File ${stamp}`);
    await page.getByRole("button", { name: "Continue" }).click();

    await page.locator('input[type="file"]').setInputFiles(EMPTY_FILE_PATH);
    await page.getByRole("button", { name: "Upload & continue" }).click();

    // Scoped to `role="alert"` — a bare `/empty/i` text match is ambiguous because the incident
    // title ("E2E Empty File …") and the uploaded filename ("empty.log") both contain "empty".
    await expect(page.getByRole("alert")).toContainText(/empty/i, { timeout: 15_000 });
  });

  test("oversized file is rejected gracefully if enforced by the stack", async ({ page }) => {
    test.setTimeout(90_000);
    const user = uniqueUser("err-oversized");
    await registerViaUi(page, user);

    const stamp = Date.now().toString(36);
    const projectName = `E2E Errors Project ${stamp}`;
    await createProjectViaUi(page, projectName, `E2EERR${stamp}`.toUpperCase().slice(0, 20));

    await page.goto("/incidents/new");
    await page.getByLabel(/^Project/).selectOption({ label: projectName });
    await page.getByLabel(/^Title/).fill(`E2E Oversized File ${stamp}`);
    await page.getByRole("button", { name: "Continue" }).click();

    await page.locator('input[type="file"]').setInputFiles(getOversizedFilePath());
    await page.getByRole("button", { name: "Upload & continue" }).click();

    // Backend enforces MAX_UPLOAD_SIZE_BYTES (10 MB default, see `.env`) and returns HTTP 413.
    // Scoped to `role="alert"` for the same reason as the other file-rejection assertions above.
    await expect(page.getByRole("alert")).toContainText(/exceeds maximum size|too large|file upload failed/i, {
      timeout: 30_000,
    });
  });

  test("/403 and an unknown route render their dedicated pages", async ({ page }) => {
    const user = uniqueUser("err-notfound");
    await registerViaUi(page, user);

    await page.goto("/403");
    await expect(page.getByRole("heading", { name: "Access restricted" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Back to dashboard" })).toBeVisible();

    await page.goto("/this-route-does-not-exist");
    await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  });

  test("an expired/cleared session redirects to login when visiting a protected route", async ({ page }) => {
    const user = uniqueUser("err-expired");
    await registerViaUi(page, user);
    await expect(page).toHaveURL(/\/dashboard$/);

    await page.evaluate(() => sessionStorage.removeItem("devguard.session"));
    await page.goto("/dashboard");

    await expect(page).toHaveURL(/\/login(\?.*)?$/);
    await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  });

  test("a fresh login after session clear restores access", async ({ page }) => {
    const user = uniqueUser("err-relogin");
    await registerViaUi(page, user);
    await page.evaluate(() => sessionStorage.removeItem("devguard.session"));
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login(\?.*)?$/);

    await loginViaUi(page, user);
    await expect(page).toHaveURL(/\/dashboard$/);
  });
});
