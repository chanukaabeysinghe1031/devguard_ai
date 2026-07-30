import { expect, type Page } from "@playwright/test";

export interface TestUser {
  email: string;
  password: string;
  fullName: string;
}

let sequence = 0;

/**
 * Generates a unique test user with a timestamped email so parallel/repeat runs never collide.
 * Uses `example.com` rather than a `.test`/`.invalid`/etc RFC 2606 reserved TLD, since the
 * backend's `EmailStr` validation (via `email-validator`) explicitly rejects special-use domains.
 */
export function uniqueUser(prefix = "e2e-user"): TestUser {
  sequence += 1;
  const stamp = `${Date.now()}-${sequence}-${Math.floor(Math.random() * 10_000)}`;
  return {
    email: `${prefix}.${stamp}@example.com`,
    password: "E2eTestPass123!",
    fullName: `E2E Test User ${stamp}`,
  };
}

/** Registers a new user via the UI. Registration auto-creates an owned organization and signs in. */
export async function registerViaUi(page: Page, user: TestUser): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("Full name").fill(user.fullName);
  await page.getByLabel("Email").fill(user.email);
  // Required fields render a trailing "*" inside the <label> (see Input.tsx), so the accessible
  // name is actually "Password*" — an exact match would never succeed. A "starts with" regex
  // avoids that while still disambiguating from the separate "Confirm password" field.
  await page.getByLabel(/^Password/).fill(user.password);
  await page.getByLabel("Confirm password").fill(user.password);
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL("**/dashboard", { timeout: 30_000 });
}

/** Logs in an existing user via the UI login form. */
export async function loginViaUi(page: Page, user: Pick<TestUser, "email" | "password">): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel(/^Password/).fill(user.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/dashboard", { timeout: 30_000 });
}

/** Logs out via the account menu in the top bar. */
export async function logoutViaUi(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await page.waitForURL("**/login", { timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
}
