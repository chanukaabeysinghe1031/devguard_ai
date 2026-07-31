# Phase 5C — Architecture Audit & Migration Plan

**Status:** Phase 5C.0–5C.4 implemented (invitations link-only; System nav isolated; workspace register UX)  
**Date:** 2026-07-31  
**Authority:** `MASTER_ARCHITECTURE.md` → `PROJECT_CONSTITUTION.md` → `DATABASE_ARCHITECTURE.md` → ADRs  

### Approved decisions (2026-07-31)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Roles | **Option A** — keep frozen roles; UX maps `organization_admin` ≈ Project Manager + Org Admin. No `project_manager`. |
| 2 | Registration | Keep auto personal org + owner; redesign UX as “Create workspace/organization”. |
| 3 | Invitations | Secure invite **links** first (copy URL); **no SMTP** in 5C. |
| 4 | Denormalize `organization_id` | **Yes** on incidents, notifications, webhook_deliveries, incident_events (timeline); audit_logs already has it. |
| 5 | Proceed | Approved for 5C.0 → 5C.1 (`010`) → later UX/invites/platform isolation. |

**Additional:** Organization Settings IA (Profile, Members, Invitations, GitHub Integrations, …); System Admin only for `platform_admin`. Org-level GitHub installations already exist (`github_installations.organization_id`); project connections select among them — reinforce in Organization UX (5C.4), do not duplicate credential model.

---

## Executive verdict

DevGuard AI is **already organization-ready**, not single-tenant.

What exists today is an MSc / enterprise-MVP multi-tenant core:

- `organizations` + `organization_members` with frozen RBAC
- JWT auth + `X-Organization-Id` tenancy header
- Projects, GitHub installations/connections scoped by `organization_id`
- Incidents / pipeline / AI artifacts scoped **via project → organization**
- Registration already creates a personal org + `organization_owner`

Phase 5C is therefore primarily a **product and completeness upgrade** (onboarding, invitations, org profile fields, nav IA, platform-admin isolation, hardening), **not** a greenfield multi-tenant rewrite.

**Do not duplicate** org models, membership services, auth deps, GitHub providers, or incident APIs.

---

## Part 1 — Audit summary

### 1.1 Backend / database (what already exists)

| Asset | Location | Notes |
|-------|----------|--------|
| Organization | `models/organization.py`, migration `002` | `id`, `name`, `slug`, `plan`, `status`, timestamps, `archived_at` |
| OrganizationMember | `models/organization_member.py` | `organization_id`, `user_id`, `role` enum, `joined_at`, `is_active` |
| User | `models/user.py` | Platform identity; `platform_role`; **no** `organization_id` on user |
| Frozen org roles | `domain/enums.py` | `organization_owner`, `organization_admin`, `engineer`, `viewer` |
| Platform role | `users.platform_role` | `platform_admin` \| `none` |
| Auth deps | `api/deps/auth.py`, `api/deps/access.py` | Bearer JWT; `X-Organization-Id`; `require_org_reader/writer/admin`; project org access |
| Org service | `organization_service.py` | Create default org on register; list/add/update/deactivate members (by **existing email**) |
| GitHub tenancy | migration `009`, setup/ingestion services | Installations + connections have `organization_id` |
| Seed | `seed.py` | Bootstrap default org + owner when `BOOTSTRAP_ENABLED` |

**Direct `organization_id` today:** `organization_members`, `projects`, `github_installations`, `github_repository_connections`, `audit_logs` (nullable).

**Indirect org scope (via project):** incidents, pipeline_runs, uploaded_files, analysis_runs, predictions, evidence, recommendations, reports, feedback, project_integrations.

**Not org-columned (by design / gap):** `notifications` (user-scoped), `webhook_deliveries` (delivery ledger), global KB / model_versions / failure_categories.

**Missing vs Phase 5C wish-list:** invitations table, permission ACL table, org profile fields (`company_name`, logo, website, industry, country, timezone), `invited_by` on members, dedicated Roles entity (roles are enums today).

### 1.2 Authentication / authorization

```text
Register/Login
  → JWT access (sub=user only; no org claim)
  → memberships[] in auth response
  → client stores one organizationId
  → every business request: Authorization + X-Organization-Id
  → membership + role check
  → resource must belong to that organization (via project join or direct org_id)
```

Platform admin bypasses membership role checks but still requires a valid org header for org-scoped routes.

### 1.3 Frontend

| Area | Status |
|------|--------|
| Login / register | Works; register auto-creates org (hidden from UX) |
| Create / Join Organization flows | **Missing** |
| Invitations UI | **Missing** (Admin → Users adds existing email) |
| Org settings | Partial (`/settings/organization` — name edit + members list) |
| Org switcher | **Missing** (session picks first active membership) |
| Admin nav | Shown to `organization_owner` / `organization_admin`; mixes org admin with platform stubs |
| GitHub manage | Owner/admin only (UI + backend `require_org_admin`) |
| Platform admin isolation | **Weak** — `platform_admin` passes all `hasAnyRole` checks |

### 1.4 What must not break (regression surface)

Auth, Phase 5A incident UI, AI analysis, manual upload, GitHub App install/webhook/incident automation, notifications, analytics/evaluation read paths, projects, history, reports, Docker + migrations `001`–`009`, OpenAPI contracts already consumed by frontend/e2e.

---

## Part 2 — Hard conflict: frozen roles

### Constitution / DB architecture (frozen v1.0)

| Role | Scope |
|------|--------|
| `platform_admin` | Platform (on `users`) |
| `organization_owner` | Organization |
| `organization_admin` | Organization |
| `engineer` | Organization |
| `viewer` | Organization |

**Project rules:** changing frozen org roles requires **separate explicit user approval**.

### Phase 5C request

| Requested | Conflict |
|-----------|----------|
| Organization Admin | Maps loosely to `organization_admin` (owner remains highest) |
| **Project Manager** | **Does not exist** in frozen model |
| Engineer | Already `engineer` |
| Viewer | Already `viewer` |
| System Administrator | Already `platform_admin` |

### Recommended role strategy (needs your choice)

**Option A — Prefer (no freeze break):** keep frozen role **codes**; improve **labels/UX** and permission matrix documentation.

| UX label | Stored role | GitHub configure | Invite members | Incidents write |
|----------|-------------|------------------|----------------|-----------------|
| Organization Owner | `organization_owner` | Yes | Yes | Yes |
| Organization Admin | `organization_admin` | Yes | Yes | Yes |
| Engineer | `engineer` | No | No | Yes |
| Viewer | `viewer` | No | No | Read |

Map requested “Project Manager” capabilities onto **`organization_admin`** (integrations + incidents + analytics) **or** split UI permissions without a new DB role (not recommended long-term).

**Option B — Freeze change (requires written approval):** add `project_manager` to `OrganizationRole` enum + Alembic enum alter + all guards/tests/docs. Higher risk; constitution amendment required.

**This plan assumes Option A unless you explicitly approve Option B.**

---

## Part 3 — Migration plan (phased; evolve existing assets)

### Guiding principles

1. Reuse `organizations`, `organization_members`, auth deps, GitHub services.  
2. Prefer **nullable additive columns** + new tables; no `docker compose down -v`.  
3. Keep indirect org scoping via `project_id` unless a concrete isolation bug requires denormalized `organization_id`.  
4. No Celery / ZIP / billing implementation (billing = placeholder only).  
5. Platform admin stays on `users.platform_role`, never as org membership.

---

### Phase 5C.0 — Baseline freeze & regression harness (no schema)

- Tag / document current HEAD as Phase 5C baseline.  
- Confirm green: backend pytest (esp. auth, org isolation, GitHub), frontend vitest/build, Playwright critical workflow.  
- Inventory OpenAPI paths that will gain invitation/onboarding endpoints.

**Exit:** known-good suite; no behavior change.

---

### Phase 5C.1 — Schema extensions (migration `010`)

**Extend `organizations` (additive):**

| Column | Notes |
|--------|--------|
| `company_name` | nullable → backfill from `name` |
| `description` | nullable |
| `website` | nullable |
| `industry` | nullable |
| `country` | nullable |
| `timezone` | nullable, default `UTC` |
| `logo_url` | nullable (store URL/path; upload later optional) |

Keep existing `slug`, `plan`, `status`. Do **not** rename `name`.

**Extend `organization_members` (additive):**

| Column | Notes |
|--------|--------|
| `invited_by` | nullable FK → `users.id` |

Keep enum `role` (Option A). Keep `is_active` (maps to requested `active`).

**New table `organization_invitations`:**

| Column | Notes |
|--------|--------|
| `id` | UUID PK |
| `organization_id` | FK CASCADE |
| `email` | CITEXT/VARCHAR |
| `role` | same org role enum (**not** project_manager unless Option B) |
| `token_hash` | store hash only |
| `invited_by` | FK user |
| `expires_at` | timestamptz |
| `accepted_at` | nullable |
| `revoked_at` | nullable |
| `created_at` | |

Unique partial index on `(organization_id, lower(email))` where not accepted/revoked (design in impl).

**Do not create** separate `roles` / `permissions` tables in 5C.1 unless you approve a full ACL redesign (out of MSc MVP; contradicts coarse RBAC already shipped).

**Optional hardening (only if audit finds isolation bugs):** denormalize `organization_id` onto `notifications` and/or `webhook_deliveries`. Default plan: **filter notifications by incident→project→org** in service layer first; add column only if needed.

**Data migration:** existing rows keep working; backfill `company_name = name` where null. No “create Default Organization” wipe — existing orgs/memberships/projects/GitHub rows already exist. Bootstrap seed remains for empty DBs.

**Exit:** `alembic upgrade head` → `010`; existing data intact; GitHub + incidents still green.

---

### Phase 5C.2 — Authorization matrix (code, no role freeze break)

Document and enforce consistently:

| Capability | owner | admin | engineer | viewer | platform_admin |
|------------|-------|-------|----------|--------|----------------|
| Org profile edit | ✓ | ✓ | | | bypass |
| Invite / deactivate members | ✓ | ✓ | | | bypass |
| Manage projects | ✓ | ✓ | create? (today writer) | | bypass |
| Configure GitHub | ✓ | ✓ | | | bypass |
| Create incidents / upload / analyse | ✓ | ✓ | ✓ | | bypass |
| Resolve / assign | ✓ | ✓ | ✓ | | bypass |
| Read dashboards / incidents | ✓ | ✓ | ✓ | ✓ | bypass |
| Platform health / models / global audit | | | | | ✓ only |

Align frontend `RequireRole` with backend (close writer/viewer UI gaps without inventing roles).

**Exit:** isolation tests + role matrix tests pass; GitHub still admin-only.

---

### Phase 5C.3 — Onboarding & invitations APIs

Reuse `AuthService` / `OrganizationService`; extend rather than replace.

New/adjusted endpoints (illustrative; exact paths follow API_SPEC style):

- `POST /auth/register-organization` — create org + first owner user + tokens (or two-step: create user then org)  
- Keep `POST /auth/register` for backward compatibility **or** deprecate behind flag after UI cutover (prefer compatibility: old register continues creating personal org)  
- `POST /organizations/{id}/invitations`  
- `POST /invitations/{token}/accept`  
- `POST /invitations/{token}/resend` (admin)  
- `DELETE` / revoke invitation  

Email: start with **logged invite URL + optional SMTP stub** if email provider not configured (do not block MSc on real mail); template in docs.

**Exit:** API tests for invite lifecycle + cross-org rejection.

---

### Phase 5C.4 — Frontend product IA

**Landing / auth:**

- Entry: Create Organization | Join Organization (invite link)  
- Multi-step Create Organization wizard (details → admin → create)  
- Accept invitation + set password screens  

**Replace org-facing “Admin” menu** with **Organization** section:

- Profile, Members, Invitations, (Roles = read-only matrix), GitHub (link to project integrations), Notification settings, Audit (org-scoped when API exists), Billing placeholder  

**Platform / System admin** (only `platform_role == platform_admin`):

- Separate **System** nav: Health, Models (deferred), Global settings placeholder, System metrics placeholder  
- Must **not** appear for normal org users  
- Fix `hasAnyRole` so platform admin does **not** silently impersonate org roles in UI labels; use explicit `isPlatformAdmin` for System nav only  

**Org switcher:** future-ready stub (show current org name; multi-org switch deferred unless memberships > 1 and approved).

**Exit:** Playwright onboarding + members/invite smoke; critical incident + GitHub e2e still pass.

---

### Phase 5C.5 — Hardening & docs

- Notification org filtering; webhook delivery org attribution if required  
- OpenAPI regen  
- Update README, USER_MANUAL, ER/sequence diagrams, role matrix, migration guide  
- Quality gates: ruff, mypy, pytest, lint, vitest, build, Playwright, Docker, alembic current  

**Exit:** Phase 5C success criteria checklist signed off.

---

## Part 4 — Explicit non-goals (this phase)

- Billing implementation  
- SSO / SAML  
- DB row-level security (Postgres RLS)  
- Per-tenant knowledge bases  
- Rewriting AI pipeline or GitHub provider  
- Introducing `analyst` or Celery  
- Destroying volumes / recreating production DB  

---

## Part 5 — Risk register

| Risk | Mitigation |
|------|------------|
| Role freeze break (`project_manager`) | Option A mapping; require written approval for Option B |
| Breaking register/e2e | Keep legacy register path; add parallel create-org flow |
| Double org models | Extend existing tables only |
| Notifications leak across orgs | Service-layer filter via incident/project; tests |
| Platform admin seeing org Admin | Split System vs Organization nav |
| Large denormalized `organization_id` migration | Defer; join path already used everywhere |
| Invite email dependency | Token URL + optional mailer |

---

## Part 6 — Approval gates (required before coding)

Please reply with decisions:

1. **Role model:** **Option A** (keep frozen roles; UX labels) or **Option B** (add `project_manager` — constitution change)?  
2. **Legacy `POST /auth/register`:** keep creating personal org (**recommended**) or replace entirely with Create Organization wizard?  
3. **Invitations email:** log/link-only for local MSc first, or require SMTP now?  
4. **Denormalize `organization_id`** onto incidents/notifications/webhooks in `010`, or keep join-based scoping + service filters?  
5. **Proceed to implement Phase 5C.0 + 5C.1** after the above?

---

## Part 7 — Success criteria (definition of done)

- New customer: Landing → Create Organization → Admin → Dashboard → Project → GitHub → auto incident → Invite engineer → collaborate → resolve  
- Cross-org access denied in API tests  
- No regression: AI analysis, GitHub automation, incident management, auth  
- Platform System nav visible only to `platform_admin`  
- Org users see Organization IA, not platform admin stubs  
- Migration `010` upgrades live DB without data loss  
- Quality gates green  

---

## Appendix — Key file index (reuse these)

```
backend/app/infrastructure/database/models/organization.py
backend/app/infrastructure/database/models/organization_member.py
backend/app/infrastructure/database/models/user.py
backend/app/domain/enums.py
backend/app/api/deps/auth.py
backend/app/api/deps/access.py
backend/app/application/services/organization_service.py
backend/app/application/services/auth_service.py
backend/app/application/services/github_setup_service.py
backend/alembic/versions/002_org_project_foundation.py
backend/alembic/versions/009_github_ingestion.py
frontend/src/hooks/useAuth.tsx
frontend/src/api/client.ts
frontend/src/components/layout/navConfig.ts
frontend/src/pages/admin/UsersPage.tsx
frontend/src/pages/settings/OrganizationSettingsPage.tsx
frontend/src/pages/auth/RegisterPage.tsx
docs/DATABASE_ARCHITECTURE.md §5.1–5.3
docs/PROJECT_CONSTITUTION.md (frozen roles)
```
