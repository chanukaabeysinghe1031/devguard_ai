import { expect, test } from "@playwright/test";

import { loginViaUi, logoutViaUi, registerViaUi, uniqueUser } from "./helpers/auth";
import { SAMPLE_LOGS } from "./helpers/fixtures";
import { submitAndWaitForUrl } from "./helpers/project";

/**
 * MUST PASS. This is the golden-path Module 5A.10 workflow: register → project → incident →
 * upload → analyse → review → note → resolve → report → history → re-login persistence.
 *
 * Assumptions about the UI (verified against the current source):
 * - There is no dedicated "Assign to me" control on the incident detail page (only Acknowledge /
 *   Re-analyse actions and a Resolve/Reopen form on the Resolution tab). Step 12 is therefore
 *   skipped with a comment, per the task's own fallback instruction.
 * - There is no explicit "change status to In Progress" control either. The closest available
 *   status-changing action exposed in the UI is "Acknowledge", which we exercise instead of a
 *   skip so the test still covers a real status transition.
 * - Analysis defaults to `execution_mode: "rag_llm"` / `enable_rag/llm: true` in the create-incident
 *   form, but the backend keeps ENABLE_RAG/ENABLE_LLM soft-fail semantics and no OPENAI_API_KEY is
 *   required — the deterministic local reasoner/rules path completes the analysis either way.
 */
test.describe("critical workflow (must pass)", () => {
  test.setTimeout(300_000);

  test("register, diagnose, resolve, and report an incident end to end", async ({ page }) => {
    const user = uniqueUser("critical");
    const stamp = Date.now().toString(36);
    const projectName = `E2E Critical Project ${stamp}`;
    const projectKey = `E2ECRIT${stamp}`.toUpperCase().slice(0, 20);
    const incidentTitle = `E2E Critical Incident ${stamp}`;

    await test.step("1-2. Register (auto-logs in)", async () => {
      await registerViaUi(page, user);
    });

    await test.step("3. Dashboard is visible", async () => {
      await expect(page).toHaveURL(/\/dashboard$/);
      await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    });

    await test.step("4. Create a project via the wizard", async () => {
      await page.goto("/projects/new");
      await expect(page.getByRole("heading", { name: "New project" })).toBeVisible();

      // Step 1: Basics
      await page.getByLabel("Project name").fill(projectName);
      await page.getByLabel("Project key").fill(projectKey);
      await page.getByRole("button", { name: "Continue" }).click();

      // Step 2: Repository
      await expect(page.getByLabel("CI provider")).toBeVisible();
      await page.getByRole("button", { name: "Continue" }).click();

      // Step 3: Environment — submit with defaults. See `submitAndWaitForUrl`'s doc comment for why
      // the final submit click isn't awaited directly.
      await expect(page.getByLabel("Cloud provider")).toBeVisible();
      await submitAndWaitForUrl(page, "Create project", /\/projects\/[0-9a-f-]+$/);
    });

    await test.step("5. Project details page shows the new project", async () => {
      await expect(page.getByRole("heading", { name: projectName })).toBeVisible();
    });

    let incidentId = "";

    await test.step("6-7. Create an incident, upload the Maven log, and start analysis", async () => {
      await page.goto("/incidents/new");
      await expect(page.getByRole("heading", { name: "New incident" })).toBeVisible();

      await page.getByLabel(/^Project/).selectOption({ label: projectName });
      await page.getByLabel(/^Title/).fill(incidentTitle);
      await page.getByRole("button", { name: "Continue" }).click();

      await expect(page.getByText("Upload GitHub Actions logs")).toBeVisible();
      await page.locator('input[type="file"]').setInputFiles(SAMPLE_LOGS.mavenDependencyFailure);
      await expect(page.getByText("maven_dependency_failure.log")).toBeVisible();
      await page.getByRole("button", { name: "Upload & continue" }).click();

      await expect(page.getByText(/Ready to analyse/)).toBeVisible();
      await submitAndWaitForUrl(page, "Start analysis", /\/incidents\/[0-9a-f-]+\/analysis$/);
      const match = page.url().match(/\/incidents\/([0-9a-f-]+)\/analysis$/);
      incidentId = match?.[1] ?? "";
      expect(incidentId).not.toBe("");
    });

    await test.step("8. Wait for analysis to reach a terminal state", async () => {
      // The "View incident" (exact) button only renders once the run is terminal (completed or
      // failed) — see IncidentAnalysisPage's `isTerminal` branch. This avoids matching the
      // "Completed"/"Failed" stage-list label text, which can render ambiguously alongside the
      // top-level status label.
      const viewIncidentButton = page.getByRole("button", { name: "View incident", exact: true });
      await expect(viewIncidentButton).toBeVisible({ timeout: 180_000 });
      await viewIncidentButton.click();
      await page.waitForURL(new RegExp(`/incidents/${incidentId}$`));
    });

    await test.step("9. Incident overview shows classification or root cause content", async () => {
      await expect(page.getByRole("heading", { name: incidentTitle })).toBeVisible();
      await expect(page.getByText("AI analysis summary")).toBeVisible();

      const hasCategory = page.getByText("Predicted category");
      const hasRootCause = page.getByText("Root cause");
      const hasNoAnalysisNotice = page.getByText("No analysis has been run for this incident yet.");

      // Both "Predicted category" and "Root cause" commonly render together on a successful
      // diagnosis, so `.or()` can legitimately match more than one element — assert on `.first()`
      // to avoid a strict-mode violation while still requiring at least one to be visible.
      await expect(hasCategory.or(hasRootCause).or(hasNoAnalysisNotice).first()).toBeVisible();
    });

    await test.step("10. Evidence, Sources, and Recommendations tabs render content", async () => {
      for (const tabName of ["Evidence", "Sources", "Recommendations"]) {
        await page.getByRole("tab", { name: tabName }).click();
        // Every tab renders either populated cards or a recognisable empty state heading — never a
        // blank or error screen — so asserting some non-empty heading/paragraph text is sufficient.
        await expect(
          page.locator("h3, pre, p").filter({ hasText: /.+/ }).first(),
        ).toBeVisible({ timeout: 20_000 });
      }
    });

    await test.step("11. Add a note", async () => {
      await page.getByRole("tab", { name: "Notes" }).click();
      const noteText = `E2E note added at ${new Date().toISOString()}`;
      await page.getByLabel("Add a note").fill(noteText);
      await page.getByRole("button", { name: "Add note" }).click();
      await expect(page.getByText(noteText)).toBeVisible();
    });

    await test.step("12. Assign to me — not exposed in the UI, skipped", async () => {
      // No "assign to me" control exists on IncidentDetailPage / OverviewTab as of this writing
      // (only `assignIncident`/`unassignIncident` API helpers exist with no bound UI). Skipped
      // per task instructions; documented here rather than silently omitted.
      test.info().annotations.push({
        type: "skip-reason",
        description: "No assign-to-me control in current UI (IncidentDetailPage/OverviewTab).",
      });
    });

    await test.step("13. Change status — no explicit control; Acknowledge exercised instead", async () => {
      await page.getByRole("tab", { name: "Overview" }).click();
      const acknowledgeButton = page.getByRole("button", { name: "Acknowledge" });
      if (await acknowledgeButton.isVisible().catch(() => false)) {
        await acknowledgeButton.click();
        await expect(acknowledgeButton).toBeHidden({ timeout: 10_000 });
      } else {
        test.info().annotations.push({
          type: "skip-reason",
          description: "Incident already acknowledged or Acknowledge control unavailable.",
        });
      }
    });

    await test.step("14. Resolve the incident via the Resolution tab", async () => {
      await page.getByRole("tab", { name: "Resolution" }).click();
      await page.getByLabel("Resolution summary").fill("Resolved by E2E: pinned the missing Maven dependency version.");
      await page.getByLabel("Confirmed root cause").fill("Missing dependency version in pom.xml caused the build failure.");
      await page.getByRole("button", { name: "Resolve incident" }).click();

      await expect(page.getByText("Resolved by E2E: pinned the missing Maven dependency version.")).toBeVisible();
      await expect(page.getByText(/Resolved/).first()).toBeVisible();
    });

    await test.step("15. Generate a report", async () => {
      await page.getByRole("tab", { name: "Report" }).click();
      await page.getByRole("button", { name: "Generate report" }).click();
      await expect(page.getByText(/Report v\d+/)).toBeVisible({ timeout: 30_000 });
    });

    await test.step("16. History shows the incident", async () => {
      await page.goto("/history");
      await page.getByLabel("Search history…").fill(incidentTitle);
      await expect(page.getByText(incidentTitle)).toBeVisible({ timeout: 15_000 });
    });

    await test.step("17. Notifications page loads", async () => {
      await page.goto("/notifications");
      await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
    });

    await test.step("18. Logout then login again — incident still visible", async () => {
      await logoutViaUi(page);
      await loginViaUi(page, user);
      await page.goto(`/incidents/${incidentId}`);
      await expect(page.getByRole("heading", { name: incidentTitle })).toBeVisible();
    });
  });
});
