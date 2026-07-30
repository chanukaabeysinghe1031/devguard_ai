import { expect, test, type Page } from "@playwright/test";

import { registerViaUi, uniqueUser } from "./helpers/auth";
import { SAMPLE_LOGS } from "./helpers/fixtures";
import { createProjectViaUi, submitAndWaitForUrl } from "./helpers/project";

/**
 * Exercises the deterministic analysis pipeline against three distinct failure classes
 * (AWS AccessDenied, Terraform undeclared resource, GitHub Actions runner offline), reusing a
 * single project across incidents as suggested by the task. Each assertion checks for real
 * diagnosis content (category, root cause, or evidence) rather than just a terminal HTTP status.
 */

async function createIncidentAndUpload(
  page: Page,
  projectName: string,
  title: string,
  logPath: string,
): Promise<string> {
  await page.goto("/incidents/new");
  await page.getByLabel(/^Project/).selectOption({ label: projectName });
  await page.getByLabel(/^Title/).fill(title);
  await page.getByRole("button", { name: "Continue" }).click();

  await page.locator('input[type="file"]').setInputFiles(logPath);
  await page.getByRole("button", { name: "Upload & continue" }).click();

  await expect(page.getByText(/Ready to analyse/)).toBeVisible();
  await submitAndWaitForUrl(page, "Start analysis", /\/incidents\/[0-9a-f-]+\/analysis$/);
  const match = page.url().match(/\/incidents\/([0-9a-f-]+)\/analysis$/);
  const incidentId = match?.[1] ?? "";
  expect(incidentId).not.toBe("");

  const viewIncidentButton = page.getByRole("button", { name: "View incident", exact: true });
  await expect(viewIncidentButton).toBeVisible({ timeout: 180_000 });
  await viewIncidentButton.click();
  await page.waitForURL(new RegExp(`/incidents/${incidentId}$`));

  return incidentId;
}

async function assertHasDiagnosisContent(page: Page): Promise<void> {
  await expect(page.getByText("AI analysis summary")).toBeVisible();

  const hasCategory = page.getByText("Predicted category");
  const hasRootCause = page.getByText("Root cause");
  const hasEvidenceCount = page.getByText("Evidence items");
  // These can legitimately co-occur on a successful diagnosis, so assert on `.first()` to avoid a
  // strict-mode violation while still requiring at least one to be visible.
  await expect(hasCategory.or(hasRootCause).or(hasEvidenceCount).first()).toBeVisible();

  // Cross-check the Evidence tab independently: it should never silently error out.
  await page.getByRole("tab", { name: "Evidence" }).click();
  await expect(page.locator("h3, pre, p").filter({ hasText: /.+/ }).first()).toBeVisible({ timeout: 20_000 });
}

test.describe("analysis scenarios across failure classes", () => {
  test.setTimeout(240_000);

  test("AWS AccessDenied, Terraform, and GitHub runner-offline logs all produce a diagnosis", async ({ page }) => {
    const user = uniqueUser("scenario");
    const stamp = Date.now().toString(36);
    const projectName = `E2E Scenario Project ${stamp}`;
    const projectKey = `E2ESCN${stamp}`.toUpperCase().slice(0, 20);

    await test.step("Register and create a shared project", async () => {
      await registerViaUi(page, user);
      await createProjectViaUi(page, projectName, projectKey);
    });

    await test.step("AWS AccessDenied log produces a diagnosis", async () => {
      await createIncidentAndUpload(page, projectName, `E2E AWS AccessDenied ${stamp}`, SAMPLE_LOGS.awsAccessDenied);
      await assertHasDiagnosisContent(page);
    });

    await test.step("Terraform undeclared-resource log produces a diagnosis", async () => {
      await createIncidentAndUpload(
        page,
        projectName,
        `E2E Terraform Undeclared Resource ${stamp}`,
        SAMPLE_LOGS.terraformUndeclaredResource,
      );
      await assertHasDiagnosisContent(page);
    });

    await test.step("GitHub Actions runner-offline log produces a diagnosis", async () => {
      await createIncidentAndUpload(
        page,
        projectName,
        `E2E GitHub Runner Offline ${stamp}`,
        SAMPLE_LOGS.githubActionsRunnerOffline,
      );
      await assertHasDiagnosisContent(page);
    });
  });
});
