import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { test } from "@playwright/test";

import { registerViaUi, uniqueUser } from "./helpers/auth";
import { createProjectViaUi } from "./helpers/project";

/**
 * Captures reference screenshots of key screens at three breakpoints for the Phase 5A visual
 * evidence pack. Run via `npm run test:e2e:screenshots`.
 */

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENSHOTS_DIR = path.resolve(__dirname, "../../reports/phase5a/screenshots");

const VIEWPORTS = [
  { label: "375x812", width: 375, height: 812 },
  { label: "768x1024", width: 768, height: 1024 },
  { label: "1440x900", width: 1440, height: 900 },
] as const;

const AUTHENTICATED_PAGES: Array<{ name: string; path: string }> = [
  { name: "dashboard", path: "/dashboard" },
  { name: "projects", path: "/projects" },
  { name: "incidents", path: "/incidents" },
  { name: "history", path: "/history" },
  { name: "reports", path: "/reports" },
  { name: "notifications", path: "/notifications" },
];

test.beforeAll(() => {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
});

test.describe("visual capture — key pages", () => {
  for (const viewport of VIEWPORTS) {
    test(`captures key pages at ${viewport.label}`, async ({ page }) => {
      test.setTimeout(90_000);
      await page.setViewportSize({ width: viewport.width, height: viewport.height });

      // Unauthenticated login screen, captured before any session exists.
      await page.goto("/login");
      await page.screenshot({
        path: path.join(SCREENSHOTS_DIR, `login-${viewport.label}.png`),
        fullPage: true,
      });

      const user = uniqueUser(`visual-${viewport.width}`);
      await registerViaUi(page, user);

      // Minimal seed so dashboard/projects/incidents render populated states rather than empty ones.
      const stamp = Date.now().toString(36);
      await createProjectViaUi(page, `E2E Visual Project ${stamp}`, `E2EVIS${stamp}`.toUpperCase().slice(0, 20));

      for (const target of AUTHENTICATED_PAGES) {
        await page.goto(target.path);
        await page.waitForLoadState("networkidle").catch(() => undefined);
        await page.screenshot({
          path: path.join(SCREENSHOTS_DIR, `${target.name}-${viewport.label}.png`),
          fullPage: true,
        });
      }
    });
  }
});
