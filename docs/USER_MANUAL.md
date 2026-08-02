# DevGuard AI — User Manual (Phase 5A)

## Start the stack

```bash
docker compose up -d --build
```

- UI: http://localhost:5173  
- API: http://localhost:8000/api/v1  
- Health: http://localhost:8000/api/v1/health  

Use **Register** / **Login**, then Dashboard → Projects → Incidents. Prefer `/incidents/new` ( `/diagnose` redirects there ).

Global search: **⌘K** / **Ctrl+K**.

## Automated E2E

```bash
cd frontend
npm run test:e2e
```

Requires API on `:8000` and UI on `:5173`. See `docs/PHASE5A_E2E_REPORT.md`.

## First session

1. Open `/register` (or `/login` if you already have an account).
2. After sign-in or workspace creation you briefly see a **branded transition** (“Signing you in” / “Creating your workspace”), then land on **Dashboard**.
3. Create a **Project** (`Projects` → Create Project). Opening a project may show a short **Loading project** screen while details, incidents, and integrations initialize.
4. Create an **Incident** (`Incidents` → Create Incident), upload a log, start analysis.
5. Watch **Analysis progress**, then review **Evidence**, **Sources**, and **Recommendations**.
6. Add **Notes**, **Assign**, change **Status**, then **Resolve**.
7. **Generate Report** from the Report tab; find the case under **History**.

Brand marks and loading UX: `docs/PHASE5D_BRANDING_AND_LOADING_UX.md`.

## Automated GitHub Actions (Phase 5B)

1. Open a project → **Integrations**.
2. Connect **GitHub Actions** (requires GitHub App configured on the server). The same GitHub App installation can be linked to more than one DevGuard organization or project; each organization only sees its own connections and incidents.
3. Select a repository and enable automatic incidents / analysis.
4. When a monitored workflow fails, DevGuard creates an incident, collects logs, and runs the same AI pipeline as manual uploads.
5. Incidents show a **GitHub** source badge and workflow context when available.

See `docs/PHASE5B_GITHUB_APP_SETUP.md`, `docs/PHASE5B_LOCAL_GITHUB_SETUP.md`, and `docs/SHARED_GITHUB_INSTALLATIONS.md`.

## Tips

- `/diagnose` redirects to the incident wizard — use the incident workflow.
- Confidence badges are heuristic, not calibrated probability.
- Source cards show High/Medium/Low relevance; weak matches are hidden.
- Admin pages (Users, System Health) require organization owner/admin.

## Sign-out

Use the avatar menu → Sign out. If you see “Invalid or expired token”, sign out and sign in again (refresh should usually renew access automatically).
