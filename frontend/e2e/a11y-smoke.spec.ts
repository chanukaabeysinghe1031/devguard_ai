import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { registerViaUi, skipBrandSplash, uniqueUser } from "./helpers/auth";

/**
 * Accessibility smoke test using axe-core. Zero *critical* impact violations are required to
 * pass; "serious" (or lower) violations are reported as test attachments for follow-up rather
 * than failing the run, since fixing them is outside this task's scope.
 */

function summarize(violations: Awaited<ReturnType<AxeBuilder["analyze"]>>["violations"]) {
  return violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    help: v.help,
    nodes: v.nodes.length,
  }));
}

test.describe("accessibility smoke (axe-core)", () => {
  test("login page has zero critical violations", async ({ page }, testInfo) => {
    await skipBrandSplash(page);
    await page.goto("/login");
    const results = await new AxeBuilder({ page }).analyze();

    const critical = results.violations.filter((v) => v.impact === "critical");
    const serious = results.violations.filter((v) => v.impact === "serious");

    await testInfo.attach("axe-violations-login.json", {
      body: JSON.stringify(summarize(results.violations), null, 2),
      contentType: "application/json",
    });

    if (serious.length > 0) {
      // eslint-disable-next-line no-console
      console.warn(`[a11y] Login page has ${serious.length} serious violation(s):`, summarize(serious));
    }

    expect(critical, `Critical a11y violations on /login: ${JSON.stringify(summarize(critical), null, 2)}`).toEqual(
      [],
    );
  });

  test("dashboard has zero critical violations", async ({ page }, testInfo) => {
    const user = uniqueUser("a11y-dashboard");
    await registerViaUi(page, user);
    await expect(page).toHaveURL(/\/dashboard$/);

    const results = await new AxeBuilder({ page }).analyze();

    const critical = results.violations.filter((v) => v.impact === "critical");
    const serious = results.violations.filter((v) => v.impact === "serious");

    await testInfo.attach("axe-violations-dashboard.json", {
      body: JSON.stringify(summarize(results.violations), null, 2),
      contentType: "application/json",
    });

    if (serious.length > 0) {
      // eslint-disable-next-line no-console
      console.warn(`[a11y] Dashboard has ${serious.length} serious violation(s):`, summarize(serious));
    }

    expect(
      critical,
      `Critical a11y violations on /dashboard: ${JSON.stringify(summarize(critical), null, 2)}`,
    ).toEqual([]);
  });
});
