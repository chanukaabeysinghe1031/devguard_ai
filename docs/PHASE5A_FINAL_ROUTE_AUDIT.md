# Phase 5A — Final Route Audit

**Module:** 5A.10  
**Branch:** `feature/enterprise-incident-management-ui`  
**Date:** 2026-07-30

Legend — **Status:** `PASS` | `PASS_WITH_LIMITS` | `DEFERRED` | `FIXED_IN_5A10`

| Route | Screen | API source | Role | Status | Missing behaviour | Test coverage | Final decision |
|-------|--------|------------|------|--------|-------------------|---------------|----------------|
| `/login` | Login | `POST /auth/login` | Public | PASS | — | E2E critical | Keep |
| `/register` | Register | `POST /auth/register` | Public | PASS | — | E2E critical | Keep |
| `/` | Redirect | — | Auth | PASS | — | E2E | Keep |
| `/dashboard` | Dashboard | `/dashboard/*` | Reader | PASS | — | E2E | Keep |
| `/projects` | Project list | `GET /projects` | Reader | PASS | — | E2E | Keep |
| `/projects/new` | Create wizard | `POST /projects` | Writer | PASS | — | E2E | Keep |
| `/projects/:id` | Project detail | project + incidents + runs | Reader | PASS | — | E2E | Keep |
| `/projects/:id/edit` | Edit project | `PATCH /projects/{id}` | Writer | PASS | — | Unit/E2E smoke | Keep |
| `/pipeline-runs/:id` | Pipeline run | `GET /pipeline-runs/{id}` | Reader | PASS | Row→incident optional | E2E optional | Keep |
| `/incidents` | Incident list | `GET /incidents` | Reader | PASS | — | E2E | Keep |
| `/incidents/new` | Create wizard | incidents/files/analyses | Writer | PASS | — | E2E critical | Keep |
| `/incidents/:id` | Detail + tabs | incident + analysis artifacts | Reader | PASS | Full VS Code evidence panes deferred | E2E | Keep |
| `/incidents/:id/analysis` | Progress | `/analyses/{id}/status` | Reader | PASS | Cancel only if API supports | E2E | Keep |
| `/history` | History | `GET /history/incidents` | Reader | PASS | — | E2E | Keep |
| `/reports` | Reports | `GET /reports` | Reader | PASS | PDF deferred | E2E | Keep |
| `/reports/:id` | Report detail | `GET /reports/{id}` | Reader | PASS | JSON view only | E2E | Keep |
| `/notifications` | Notifications | `/notifications*` | Reader | PASS | — | E2E | Keep |
| `/evaluation` | Research metrics | `GET /evaluation/latest-metrics` | Reader | PASS_WITH_LIMITS | Empty without benchmark file | E2E smoke | Keep |
| `/settings/organization` | Org settings | org APIs | Admin write | PASS | — | E2E smoke | Keep |
| `/settings/security` | Password | `change-password` | Auth | PASS | — | E2E smoke | Keep |
| `/settings/notifications` | Prefs | None (in-app defaults) | Auth | FIXED_IN_5A10 | Preference persistence deferred | Documented | Read-only explainer |
| `/profile` | Profile | `/auth/me` | Auth | PASS | — | E2E smoke | Keep |
| `/admin/users` | Members | org members | Admin | PASS | Invite email deferred | E2E admin | Keep |
| `/admin/models` | Models | No list API | Admin | DEFERRED | Registry API | Documented stub→deferred UI | Explicit deferred |
| `/admin/system-health` | Health | `/health*` | Admin | PASS | — | E2E admin | Keep |
| `/admin/audit` | Audit | No list API | Admin | DEFERRED | Writers + list | Documented | Explicit deferred |
| `/admin/evaluation` | Admin eval | CLI primary | Admin | DEFERRED | Admin write controls | Documented | Link to `/evaluation` |
| `/diagnose` | Redirect | — | Auth | PASS | — | E2E | Keep redirect |
| `/403` | Forbidden | — | Auth | PASS | — | E2E | Keep |
| `*` | 404 | — | Auth | PASS | — | E2E | Keep |
| `/error` | Recoverable error | — | Auth | FIXED_IN_5A10 | Was missing | E2E | ErrorBoundary + page |

**Orphans removed in 5A.10:** `HomePage.tsx`, `DiagnosisPage.tsx` (superseded).
