# Phase 5A — Module 5A.10 E2E Test Report

**Status:** All 19 specs passing locally (see [Results](#results)).
**Suite location:** `frontend/e2e/`
**Framework:** Playwright (`@playwright/test` 1.62.0) + `axe-core` (`@axe-core/playwright`)

## Scope

This suite exercises the deterministic, local-first DevGuard AI workflow end to end through the
real UI against a running backend, with **no dependency on OpenAI or any external API key** — the
backend's soft-fail design (Module 7/8) falls back to the deterministic rules/local reasoner path
when `OPENAI_API_KEY` is unset, so every spec below is expected to pass on stock `.env` defaults.

| Spec | Purpose | Must pass? |
|---|---|---|
| `e2e/critical-workflow.spec.ts` | Golden path: register → project → incident → upload → analyse → review tabs → note → resolve → report → history → re-login persistence | **Yes — never skip** |
| `e2e/analysis-scenarios.spec.ts` | Deterministic diagnosis across AWS AccessDenied, Terraform, and GitHub Actions runner-offline logs | Yes |
| `e2e/errors-and-auth.spec.ts` | Unsupported/empty/oversized file rejection, `/403` + unknown-route rendering, expired-session redirect | Yes |
| `e2e/responsive.spec.ts` | Layout smoke test at 375 / 768 / 1440 px | Yes |
| `e2e/visual.spec.ts` | Screenshot capture of key screens at 3 viewports into `reports/phase5a/screenshots/` | Evidence-only (not a pass/fail gate) |
| `e2e/a11y-smoke.spec.ts` | axe-core scan of Login + Dashboard; zero **critical** violations required | Yes |

## How to run

### 1. Start the backend + database

```bash
# From the repo root — brings up Postgres, backend API, and dependent services.
docker compose up -d postgres backend
# or, if running the backend directly:
cd backend && uvicorn app.main:app --reload --port 8000
```

Confirm the API is reachable:

```bash
curl -sf http://localhost:8000/api/v1/health || echo "backend not ready"
```

No `OPENAI_API_KEY` is required. Leave `.env` at its checked-in defaults.

### 2. Start the frontend dev server

```bash
cd frontend
npm install
npm run dev   # serves on http://localhost:5173 by default
```

### 3. Install Playwright browsers (first time only)

```bash
cd frontend
npx playwright install chromium --with-deps
```

### 4. Run the suite

```bash
cd frontend

# Full suite, headless, against the defaults above
npm run test:e2e

# Interactive UI mode (recommended while iterating)
npm run test:e2e:ui

# Only the visual/screenshot pack
npm run test:e2e:screenshots

# Only the must-pass critical workflow
npx playwright test e2e/critical-workflow.spec.ts

# Point at a non-default stack (CI, staging, docker-compose network, etc.)
E2E_BASE_URL=http://localhost:5173 \
E2E_API_BASE_URL=http://localhost:8000/api/v1 \
npm run test:e2e
```

Playwright HTML report, JSON results, traces, and videos are written under
`reports/phase5a/playwright/` and `reports/phase5a/playwright-report/` (gitignored — regenerate
per run). Screenshots from `visual.spec.ts` are written to `reports/phase5a/screenshots/` and are
**not** gitignored, since they're intended as Phase 5A evidence.

To view the HTML report after a run:

```bash
npx playwright show-report ../reports/phase5a/playwright-report
```

## Assumptions and known UI gaps (see also inline comments in the specs)

- **No "assign to me" control** exists on the incident detail page. `assignIncident` /
  `unassignIncident` API helpers exist in `src/api/incidentsApi.ts` but are not wired to any button
  in `IncidentDetailPage` / `OverviewTab`. The critical-workflow spec skips this step with an
  annotation rather than failing.
- **No explicit "change status to In Progress" control** exists either. The closest real,
  UI-exposed status transition is **Acknowledge**, which the critical-workflow spec exercises
  instead of a hard skip.
- **Every registered user is an `organization_owner`** of a brand-new organization
  (`AuthService.register` → `create_default_organization_for_user`). There is no self-serve
  "invite a viewer" flow in the UI, so a genuine non-admin 403 check against `/admin/models` isn't
  reachable without backend fixtures/seeding outside the scope of this suite. Per the task's own
  fallback instruction, `errors-and-auth.spec.ts` instead asserts that `/403` and an unknown route
  render their dedicated pages (both routes require being logged in first, since they're nested
  inside the `RequireAuth` route group in `router.tsx`).
- **`/403`, `/error`, and the catch-all 404 route require authentication** to actually render —
  they sit inside the same `RequireAuth`-wrapped route group as the rest of the app shell.
- Upload limits used for negative tests: `MAX_UPLOAD_SIZE_BYTES=10485760` (10 MB, from `.env`);
  the oversized fixture is generated on the fly at ~11 MB in the OS temp dir rather than committed
  to the repo.
- Allowed upload extensions are `.log`, `.txt`, `.yaml`, `.yml`, `.tf`, `.tfvars`, `.json`
  (`backend/app/domain/services/file_validation.py`); `.exe` is used as the unsupported-type fixture.
- **Registration requires a non-reserved email TLD.** The backend's `EmailStr` validation
  (`email-validator`, used by `RegisterRequest` in `backend/app/schemas/auth.py`) rejects
  RFC 2606 special-use domains such as `.test`/`.invalid`/`.example`. `uniqueUser()` in
  `e2e/helpers/auth.ts` therefore mints addresses on `example.com` (a real, deliverable-looking
  domain the validator accepts) with a timestamp+sequence+random local-part instead.
- **Self-disabling submit buttons that also navigate on success are click-flaky under Playwright.**
  `ProjectCreatePage`'s "Create project" and `IncidentCreatePage`'s "Start analysis" both set
  `isLoading` (which disables the button) the instant their mutation starts, then navigate away
  in `onSuccess`. Playwright's `.click()` can report a spurious `TimeoutError` in that exact race
  (the click is delivered and the mutation does fire, but the button disables/unmounts before
  Playwright's internal post-click verification completes). `e2e/helpers/project.ts` exports
  `submitAndWaitForUrl()`, which gives the click a short 5s timeout, swallows a timeout from it
  specifically, and treats `waitForURL` as the real success signal — this is used everywhere the
  suite submits one of these two buttons.
- Two tab-content assertions (`hasCategory.or(hasRootCause)...`) call `.first()` before
  `toBeVisible()`, since a successful diagnosis commonly renders **both** "Predicted category"
  and "Root cause" simultaneously, which is a Playwright strict-mode violation for a bare
  `.or()` chain without narrowing to one match.
- File-rejection assertions in `errors-and-auth.spec.ts` scope to `page.getByRole("alert")`
  (the `Alert` component's `role="alert"`) rather than a bare text match, since incident titles
  and uploaded filenames used in those tests can coincidentally contain the same substring as the
  expected error text (e.g. both an incident titled "E2E Empty File …" and the file "empty.log"
  match `/empty/i`). The unsupported-file-type message is also copy-specific
  ("Executable file types are not allowed.") rather than a generic "unsupported file" string, so
  the assertion matches on `/not allowed/i` instead.

## Results

Full suite run locally against the environment below (`npm run test:e2e`):

| Spec | Result | Notes |
|---|---|---|
| `critical-workflow.spec.ts` | ✅ Pass | ~13–17s; full golden path incl. re-login persistence |
| `analysis-scenarios.spec.ts` | ✅ Pass | ~18–20s; AWS/Terraform/GitHub-runner-offline all produced a diagnosis |
| `errors-and-auth.spec.ts` | ✅ Pass (6/6) | unsupported/empty/oversized rejection, `/403`, 404, expired session, re-login |
| `responsive.spec.ts` | ✅ Pass (6/6) | 375 / 768 / 1440 px × {login, dashboard} |
| `visual.spec.ts` | ✅ Pass (3/3) | Screenshots at `reports/phase5a/screenshots/` (18 PNGs: 6 pages × 3 viewports) |
| `a11y-smoke.spec.ts` | ✅ Pass (2/2) | Critical violations: 0 / Serious (documented, non-blocking): 1 on Login (1 node), 1 on Dashboard (3 nodes) — both `color-contrast` |

**Totals:** 19/19 tests passed, 0 failed, 0 skipped, ~2m0s wall clock (single worker, `fullyParallel: false`).

**Environment used for this run:**

- Backend commit / date: `b3d03bd` / 2026-07-30
- Frontend commit / date: `b3d03bd` / 2026-07-30
- `EMBEDDING_PROVIDER`: `sentence_transformers`
- `OPENAI_API_KEY` set: No (expected: No) — analyses completed via the deterministic rules/local
  reasoner path, confirming Module 7/8's soft-fail fallback works with stock `.env` defaults
- Browser: Chromium (Playwright-managed, `@playwright/test` 1.62.0)
- OS: macOS (darwin 25.5.0)

**Flakiness / follow-ups observed:**

- None outstanding. Two categories of flake were found and fixed during development (see the
  self-disabling-submit-button and strict-mode-`.or()` bullets above) — both are now handled by
  shared helpers rather than being worked around ad hoc per spec.
- `color-contrast` is flagged as **serious** (not critical) by axe-core on both Login and
  Dashboard; per the task's acceptance criteria (zero **critical** violations) this does not fail
  the suite, but it's a legitimate design-system follow-up worth triaging separately.
