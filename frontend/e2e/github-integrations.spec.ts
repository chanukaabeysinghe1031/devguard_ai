/**
 * Phase 5B — GitHub integration configuration + webhook security smoke.
 *
 * Does not call the real GitHub API. Full install→ingest UI requires a GitHub App;
 * backend FakeGitHubProvider covers end-to-end ingestion in pytest.
 */
import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";

import { uniqueUser, registerViaUi } from "./helpers/auth";
import { createProjectViaUi } from "./helpers/project";
import { API_BASE_URL } from "./helpers/env";

test.describe("GitHub integrations (Phase 5B)", () => {
  test.setTimeout(180_000);

  test("integrations page loads and shows GitHub + deferred providers", async ({ page }) => {
    const user = uniqueUser("gh-ui");
    await registerViaUi(page, user);
    const key = `GH${Date.now().toString().slice(-6)}`;
    await createProjectViaUi(page, `GH UI ${key}`, key);

    const projectId = page.url().match(/\/projects\/([0-9a-f-]+)/)?.[1];
    expect(projectId).toBeTruthy();

    await page.goto(`/projects/${projectId}/integrations`);
    await expect(page.getByRole("heading", { name: /Integrations/i })).toBeVisible();
    await expect(page.getByText(/GitHub Actions/i).first()).toBeVisible();
    await expect(page.getByText(/Manual Upload/i).first()).toBeVisible();
    await expect(page.getByText(/Coming later/i).first()).toBeVisible();
  });

  test("invalid webhook signature is rejected", async ({ request, page }) => {
    const user = uniqueUser("gh-sig");
    await registerViaUi(page, user);

    const badBody = JSON.stringify({ action: "completed" });
    const bad = await request.post(`${API_BASE_URL}/integrations/github/webhook`, {
      data: badBody,
      headers: {
        "Content-Type": "application/json",
        "X-GitHub-Event": "workflow_run",
        "X-GitHub-Delivery": randomUUID(),
        "X-Hub-Signature-256": "sha256=deadbeef",
        "User-Agent": "GitHub-Hookshot/test",
      },
    });
    expect(bad.status()).toBeGreaterThanOrEqual(400);
  });
});
