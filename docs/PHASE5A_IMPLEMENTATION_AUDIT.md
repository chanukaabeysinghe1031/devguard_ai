# Phase 5A — Implementation Audit

**Version:** 1.0  
**Date:** 2026-07-30  
**Status:** Authoritative gap matrix for Module 5A  
**Authority sources (order):** MASTER_ARCHITECTURE → PROJECT_CONSTITUTION → PROJECT_STRUCTURE → DATABASE_ARCHITECTURE → API_SPECIFICATION → AI_ARCHITECTURE → DATASET_SPECIFICATION → SCREEN_SPECIFICATION → CUSTOMER_EXPERIENCE_AND_INCIDENT_WORKFLOW_SPECIFICATION → IMPLEMENTATION_ROADMAP → DevGuardAI_UI_Prompt_Collection

**Rule:** A screen is implemented only when connected to real data, functional, validated, authorised, responsive, accessible, tested, and visually consistent. Route existence alone does **not** count.

---

## 1. Documents reviewed

| # | Document | Role |
|---|----------|------|
| 1 | `docs/MASTER_ARCHITECTURE.md` | Single source of truth |
| 2 | `docs/PROJECT_CONSTITUTION.md` | Non-negotiable rules / frozen roles |
| 3 | `docs/PROJECT_STRUCTURE.md` | Repo layout |
| 4 | `docs/DATABASE_ARCHITECTURE.md` | Schema / isolation |
| 5 | `docs/API_SPECIFICATION.md` | `/api/v1` contracts |
| 6 | `docs/AI_ARCHITECTURE.md` | Pipeline (preserve; do not rewrite) |
| 7 | `docs/DATASET_SPECIFICATION.md` | Research data (do not alter gold labels) |
| 8 | `docs/SCREEN_SPECIFICATION.md` | Approved screens |
| 9 | `docs/CUSTOMER_EXPERIENCE_AND_INCIDENT_WORKFLOW_SPECIFICATION.md` | Incident-centric journey |
| 10 | `docs/IMPLEMENTATION_ROADMAP.md` | Frontend Part 4 sequence |
| 11 | `docs/DevGuardAI_UI_Prompt_Collection.md` | Visual identity |

---

## 2. Current state summary

### Frontend (as of audit)

- Vite + React 18 + React Router 6 + Tailwind 3
- Routes: `/` (splash), `/diagnose` (auth + upload + analysis + results)
- No AppShell, TanStack Query, forms library, charts, icon library, or design-token CSS variables
- Session: `sessionStorage` JWT + org id; no refresh-token wiring; no route guards
- `/diagnose` is the **primary** product experience today (must be demoted)

### Backend (as of audit)

- Full business APIs for auth, orgs, projects, pipeline runs, incidents (CRUD, status, assign, timeline, notes, resolve/reopen), files, analyses (start/status/evidence/sources/recommendations)
- **Missing APIs** (tables exist for most): dashboard aggregates, notifications, reports, history search, audit logs, evaluation admin, global search
- AI pipeline Modules 6–9 complete — **do not rewrite**

### Database

- Core incident domain tables present and wired
- Schema-ahead (ORM + migrations, no writers/API): `notifications`, `incident_reports`, `audit_logs`, `evaluations`, `feedback`
- **No destructive migration required** for Phase 5A MVP screens that reuse existing columns; new APIs use existing tables

---

## 3. Screen / workflow implementation matrix

Legend — **Decision:** `BUILD_FE` | `BUILD_BE+FE` | `DEFER` | `REUSE` | `REDIRECT`

| Approved screen / workflow | Required workflow | Existing FE route | FE implementation | Existing API | DB support | Missing FE | Missing BE | Migration | Decision |
|----------------------------|-------------------|-------------------|-------------------|--------------|------------|------------|------------|-----------|----------|
| Login | Email/password → session | None (inline on `/diagnose`) | Partial form only | `POST /auth/login`, refresh, logout, me | Yes | Dedicated `/login`, remember UX, return-path | Refresh wiring in client | None | BUILD_FE |
| Register | Create account → login | None (inline) | Partial | `POST /auth/register` | Yes | Dedicated `/register` | None | None | BUILD_FE |
| Forgot password | Reset flow | None | None | **No API** | No | — | Full reset flow | Would need schema | DEFER (hide link) |
| App shell (sidebar/top bar) | Nav + org identity + role awareness | None | None | `/auth/me`, `/organizations/current` | Yes | Full shell | None | None | BUILD_FE |
| Dashboard | KPIs, charts, recent, activity | None | None | **Missing** dashboard endpoints | Aggregates from incidents/analyses/pipeline_runs | Full dashboard | Dashboard API suite | None | BUILD_BE+FE |
| Projects list | Search/filter/sort CRUD | None | Auto-create only in diagnose | `GET/POST /projects` | Yes | List UI | None | None | BUILD_FE |
| Create project wizard | 4-step create | None | None | `POST /projects` | Yes | Wizard | None | None | BUILD_FE |
| Project details | Overview + tabs | None | None | `GET/PATCH`, archive/restore, pipeline-runs | Yes | Detail + tabs | Optional project stats (derive) | None | BUILD_FE |
| Project edit / archive | Update + soft archive | None | None | PATCH + archive/restore | Yes | Forms/actions | None | None | BUILD_FE |
| Pipeline run details | Context + link incident | None | None | `GET /pipeline-runs/{id}` | Yes | Detail page | None | None | BUILD_FE |
| Incidents list | Filters, pagination, chips | None | Recent list on diagnose only | `GET /incidents` (rich filters) | Yes | Full list | None | None | BUILD_FE |
| Create incident wizard | Details → upload → analyse | `/diagnose` (monolith) | Technical demo only | Incidents + files + analyses | Yes | Product wizard; redirect `/diagnose` | None | None | BUILD_FE + REDIRECT |
| Analysis progress | Polled stages | Part of `/diagnose` | Works in demo | `/analyses/{id}/status` | Yes | Dedicated route under incident | None | None | BUILD_FE |
| Incident details | Header + tabs + actions | None | Results dump on diagnose | Detail + analyses + artifacts | Yes | Full workspace | Compact diagnostics (no raw JSON primary) | None | BUILD_FE |
| Evidence viewer | Multi-pane investigation | Partial cards on diagnose | Not investigation UI | `GET /analyses/{id}/evidence` | Yes | Split viewer | File content fetch if needed | None | BUILD_FE |
| Retrieved sources | Relevance-labelled cards | Partial on diagnose | Shows scores/raw-ish | `GET /analyses/{id}/sources` | Yes | Relevance bands + filtering | Soft relevance filter if missing | None | BUILD_FE (+ minor BE if needed) |
| Recommendations | Grouped Immediate/Verify/Prevent | Partial on diagnose | Duplication risk | `GET /analyses/{id}/recommendations` | Yes | Structured cards + dedupe render | Recommendation status API if lacking | Check domain | BUILD_FE |
| Timeline | Vertical events | None | None | `GET /incidents/{id}/timeline` | Yes (`incident_events`) | Timeline UI | None | None | BUILD_FE |
| Notes | CRUD notes | None | None | Notes endpoints | Yes | Notes UI | None | None | BUILD_FE |
| Assignment | Assign/unassign/me | None | None | assign/unassign + members | Yes | Assign UI | None | None | BUILD_FE |
| Resolution | Guided resolve + reopen | None | None | resolve/reopen/resolutions | Yes | Resolution wizard | None | None | BUILD_FE |
| Status transitions | Backend-enforced | None | None | `POST .../status` | Yes | Transition controls | None | None | BUILD_FE |
| Reports library | List/generate/view | None | None | **Missing** | `incident_reports` table | Reports UI | Generate/list/get/download | None (use existing table) | BUILD_BE+FE |
| Report details | Print-friendly | None | None | **Missing** | Yes | Detail view | Persist JSON/HTML path | None | BUILD_BE+FE |
| History | Searchable history | Mini recent on diagnose | Client-only historically (fixed to API) | Spec: `GET /history/incidents`; can proxy incidents | Yes | History page | History endpoint (thin) | None | BUILD_BE+FE |
| Notifications | List/read/click-through | None | None | **Missing** | `notifications` table | Centre + bell | List/read/read-all + writers on events | None | BUILD_BE+FE |
| Global search | Cmd+K projects/incidents/reports | None | None | Only `?search=` on lists | Yes | Command palette | Optional `/search` aggregate | None | BUILD_FE (compose list APIs) first; BE later if needed |
| Evaluation (research) | Metrics display | None | None | CLI/files only | `evaluations` + benchmark results | `/evaluation` read-only from files/API | Optional read API | None | BUILD_FE (read versioned metrics JSON) / DEFER admin write |
| Settings profile/security | Profile + password | None | None | `/auth/me`, change-password | Yes | Settings tabs | None | None | BUILD_FE |
| Settings notifications/appearance/AI | Prefs | None | None | Partial / none for prefs | Partial | Safe stubs or hide unsupported | Prefs API if required | Likely | DEFER unsupported prefs; show only real options |
| Profile | User card + assigned | None | None | me + incidents `assignee` filter | Yes | Profile page | None | None | BUILD_FE |
| Admin users | Org members | None | None | Org members CRUD | Yes | Admin users UI | Platform-admin listing if needed | None | BUILD_FE (org-scoped) |
| Admin AI models | Model versions | None | None | **Limited/none product API** | `model_versions` | Read-only list if API added | Read endpoint | None | BUILD_BE+FE or DEFER |
| Admin evaluation | Experiments | None | None | None | Yes | — | — | — | DEFER (research CLI) |
| Admin system health | Health cards | Partial badge | Health only | `/health`, `/health/ready` | N/A | Admin health page | Enrich ready payload safely | None | BUILD_FE (+ optional BE enrich) |
| Admin audit | Audit trail | None | None | **Missing** | `audit_logs` | Audit UI | Writers + list API | None | BUILD_BE+FE (MVP: list if rows exist) |
| 403 / 404 / error | Recoverable errors | None | None | N/A | N/A | Pages | None | None | BUILD_FE |
| `/diagnose` demotion | Not primary UX | `/diagnose` | Full demo | Same analysis APIs | Yes | Redirect → `/incidents/new` or admin playground | None | None | REDIRECT |

---

## 4. Backend gap detail (priority for 5A)

| Capability | Spec path | Priority | Approach |
|------------|-----------|----------|----------|
| Dashboard summary / trend / severity / categories / recent | `/dashboard/*` | P0 | New application service aggregating existing tables |
| Notifications list/read | `/notifications*` | P0 | Wire ORM + create on key incident/analysis events |
| Reports generate/get | `/incidents/{id}/reports`, `/reports/{id}` | P0 | Persist structured report JSON to storage_path; HTML/JSON view (no fake PDF) |
| History search | `/history/incidents` | P1 | Thin wrapper over incident filters (resolved/closed bias optional) |
| Audit log list | `/admin/audit-logs` | P2 | List existing rows; add writers on critical mutations incrementally |
| Global search | `/search` | P2 | Compose FE queries first |
| Evaluation admin | `/admin/evaluations` | P3 | Defer; FE may show `datasets/benchmark/results/latest_metrics.json` via static/docs or optional endpoint |
| Feedback / recommendation status | Spec partial | P3 | Defer unless schema already supports |

**Migration requirement:** None for core Phase 5A if existing tables are used. Alembic only if a verified column gap appears during implementation.

---

## 5. Frontend gap detail

| Area | Gap |
|------|-----|
| Design system | No CSS tokens matching approved palette; Tailwind colours outdated vs UI prompt |
| Component library | No shared Button/Table/Badge/Modal/EmptyState |
| Routing | 2 routes; need full protected route map |
| Data layer | No TanStack Query / query keys / central error map |
| Auth UX | No dedicated pages; no refresh; diagnose-coupled |
| Product modules | All SaaS modules missing except diagnosis demo |
| AI presentation | Raw runtime JSON, route label mismatches, recommendation duplication, confidence labelling |
| Tests | No component/E2E product suite for business screens |

---

## 6. AI presentation defects (fix without changing gold labels)

| Defect | Action |
|--------|--------|
| Route label vs retrieved sources | Show user-readable **effective** mode; technical route in diagnostics only |
| Weak unrelated sources | Apply relevance threshold / category filter in UI (+ existing BE filters) |
| Local reasoner vs “RAG+LLM” button copy | Label from persisted execution metadata |
| Duplicated recommendation text | Normalise summary vs details in renderer + regression test |
| 100% confidence implication | Tooltip: rule/heuristic confidence ≠ calibrated probability |

---

## 7. Implementation sequence (approved)

| Module | Scope | Status at audit |
|--------|-------|-----------------|
| 5A.1 | Audit, tokens, components, shell, guards, API foundation | **In progress** |
| 5A.2 | Auth + navigation | Pending |
| 5A.3 | Projects | Pending |
| 5A.4 | Incidents | Pending |
| 5A.5 | AI investigation UX | Pending |
| 5A.6 | Collaboration + resolution | Pending |
| 5A.7 | Dashboard + analytics | Pending |
| 5A.8 | Reports, history, notifications, search | Pending |
| 5A.9 | Settings + admin | Pending |
| 5A.10 | Responsive, a11y, tests, docs, quality gates | Pending |

---

## 8. Non-goals / preserve

- Do not rewrite AI classification, RAG, or reasoning pipeline
- Do not change benchmark gold labels or research metrics for UI cosmetics
- Do not `docker compose down -v` on live volumes
- Do not invent org role `analyst`
- ZIP upload remains gated (ADR-011)
- Module 10 multi-agent remains unapproved

---

## 9. Audit conclusion

**Backend core incident workflow is product-ready.**  
**Frontend is a diagnosis demo, not an incident-management business application.**  
**Schema is ahead of notifications/reports/audit APIs.**  

Phase 5A must: (1) build the enterprise shell and incident-centric UI on existing APIs; (2) add dashboard/notifications/reports/history APIs against existing tables; (3) demote `/diagnose`; (4) fix AI result presentation without altering research artefacts.

**Audit complete — Module 5A.1–5A.5 core implemented; Module 5A.10 quality gates remaining. See `docs/PHASE5A_TEST_REPORT.md` and `docs/PHASE5A_KNOWN_LIMITATIONS.md`.**
