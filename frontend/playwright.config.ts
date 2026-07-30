import { defineConfig, devices } from "@playwright/test";

import { BASE_URL } from "./e2e/helpers/env";

/**
 * DevGuard AI — Phase 5A Module 5A.10 Playwright configuration.
 *
 * Assumptions:
 * - The frontend dev server (Vite) is already running at E2E_BASE_URL (default http://localhost:5173).
 * - The backend API is already running at E2E_API_BASE_URL (default http://localhost:8000/api/v1),
 *   with local/deterministic analysis available (no OpenAI key required — the backend soft-fails
 *   to the deterministic rules/local reasoner path per MASTER_ARCHITECTURE Module 7/8).
 * - This config intentionally does NOT start webServers itself, since the stack (Postgres, backend,
 *   frontend) is managed via docker-compose / existing dev scripts. Start both before running tests.
 */

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../reports/phase5a/playwright",
  timeout: 120_000,
  expect: {
    timeout: 15_000,
  },
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ["list"],
    ["html", { outputFolder: "../reports/phase5a/playwright-report", open: "never" }],
    ["json", { outputFile: "../reports/phase5a/playwright/results.json" }],
  ],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
