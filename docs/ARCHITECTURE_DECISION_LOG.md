# Architecture Decision Log

**Project:** DevGuard AI  
**Purpose:** Record architecture decisions that bind implementation after approval  
**Authority:** Decisions here are subordinate to MASTER_ARCHITECTURE.md but bind the team once Status = Accepted

---

# ADR Index

| ID | Title | Status |
|----|-------|--------|
| ADR-005 | Automated GitHub Actions Incident Ingestion | Accepted |
| ADR-012 | Evolve Legacy Flat Schema to Incident-Centred Domain Model | Accepted |
| ADR-013 | Phase 5C Multi-Tenant Completeness (Roles, Invites, Org Denormalization) | Accepted |

---

# ADR-012 — Evolve Legacy Flat Schema to Incident-Centred Domain Model

## Status

**Accepted** — approved by project owner, 24 July 2026.

## Context

Module 1 delivered a working foundation (FastAPI, React shell, Docker, health endpoints, async PostgreSQL).

An early Module 2 effort then introduced Alembic revision `001_initial_schema` with **11 application tables** based on an earlier **flat ML-centric** design:

- `users`
- `uploaded_files`
- `pipeline_runs`
- `failure_categories`
- `predictions`
- `evidence_items`
- `recommendations`
- `model_versions`
- `evaluations`
- `feedback`
- `analysis_history`

That design links predictions, evidence, and recommendations primarily to `pipeline_runs` and users, without first-class organizations, projects, incidents, or analysis runs.

The **frozen** architecture (MASTER_ARCHITECTURE.md and DATABASE_ARCHITECTURE.md) requires an **incident-centred, organization-ready** domain:

```text
Organization
  → User / Membership
  → Project
  → Pipeline Run
  → Incident
  → Uploaded Files
  → Analysis Run
  → Prediction
  → Evidence
  → Retrieved Documents
  → Recommendations
  → Resolution
  → Report
```

DATABASE_ARCHITECTURE.md §9 explicitly states that existing tables should **not be discarded** — they should be **evolved**. §5.26 further states that `analysis_history` should **not** be created for the MVP (history should be derived).

Continuing feature development (auth APIs, uploads, AI) against the legacy flat schema would cement the wrong domain model and force a more expensive rewrite later.

Detailed table mapping and staged migration waves are documented in `docs/SCHEMA_EVOLUTION_PLAN.md`.

## Decision

The project will **evolve** the schema through **controlled Alembic migrations** toward the frozen incident-centred domain model.

Specifically:

1. Treat `001_initial_schema` as a **legacy baseline**, not the target architecture.
2. Do **not** continue building new product features on the legacy flat ML schema.
3. Migration 002+ and related SQLAlchemy model updates are **approved** for schema-only implementation (models + Alembic migrations + seeds + tests). Auth APIs, business APIs, AI, and frontend features remain separately gated.
4. Prefer additive, staged migrations (organizations/projects → incidents → analysis_runs → supporting tables → cleanup).
5. Reassess / deprecate `analysis_history` for MVP per DATABASE_ARCHITECTURE.
6. Recreate only the **development** database after correct migrations are authored **if** the project owner accepts Option B in the schema evolution plan (no valuable irreplaceable production data exists today).

### Accepted decisions (24 July 2026)

| Topic | Decision |
|-------|----------|
| Local development database | **Option B** — author Migrations 002–007, then recreate only the local development database / Docker volume and re-seed |
| Organization roles | Frozen set on `organization_members`: `organization_owner`, `organization_admin`, `engineer`, `viewer`. **No `analyst` role** |
| Platform admin | `platform_admin` is a **platform-level** capability (e.g. `users.is_platform_admin` or equivalent), **not** an organization membership role |
| Failure taxonomy | Keep the **11** seeded failure categories for v1.0 |
| Recommendations | Normalized `recommendation_steps` table; step types `remediation` \| `verification` \| `prevention`. Parent `recommendations` is a summary record |
| Integrations | Include `project_integrations` in **Migration 002** (no raw credentials stored) |
| Bootstrap | Idempotent **seed script** + environment variables (not Alembic data migrations) for default org / owner membership |
| Migration waves | Waves **002–007** as defined in `SCHEMA_EVOLUTION_PLAN.md` are approved |

## Alternatives Considered

### 1. Continue with the legacy schema

Keep developing auth, APIs, and AI on the current 11 tables.

**Rejected:** Violates MASTER_ARCHITECTURE and DATABASE_ARCHITECTURE; blocks correct incident lifecycle and multiple analysis runs.

### 2. Delete everything and restart

Wipe repository foundation and rebuild from scratch.

**Rejected:** Unnecessary. Module 1 foundation is sound; DATABASE_ARCHITECTURE instructs evolution, not discard.

### 3. Evolve the schema using migrations (chosen)

Add/alter tables via Alembic in stages; update ORM, repositories, and tests afterward.

**Selected:** Aligns with frozen architecture and minimizes rewrite risk.

### 4. Recreate only the development database after creating correct migrations

Author correct migrations first, then reset local Docker Postgres volume / database for a clean apply of the full chain.

**Accepted for local development (24 July 2026) as Option B.** Compatible with (3). Must **not** be done until migrations are authored and validated. Production-like data (if any later) must use transform migrations.

## Consequences

### Costs / complexity

- SQLAlchemy model refactoring
- Multi-step Alembic migration complexity
- Possible development database recreation
- Repository and future service updates
- Future API shape changes relative to any legacy assumptions
- Test fixture and seed updates
- Enum renaming / value alignment risk

### Benefits

- Correct long-term domain model and traceability
- Support for incidents and multiple analysis runs per incident
- Organization-ready MVP without multi-tenant SaaS scope creep
- Alignment with API_SPECIFICATION and SCREEN_SPECIFICATION
- Safer AI attachment points (`analysis_runs` as orchestration unit)

## Approval Requirement

This ADR is **Accepted** (project owner, 24 July 2026).

**Now permitted (schema only):**

- Alembic Migrations 002–007 per the accepted plan
- SQLAlchemy model updates aligned to the target schema
- Idempotent seed scripts and related schema tests
- Local development database recreation under **Option B** after migrations are authored and validated

**Still forbidden until separately approved:**

- Authentication / authorization APIs
- Business / upload / analysis APIs
- AI / ML / RAG / LLM modules
- Frontend feature work beyond existing shells
- New product features on the legacy flat schema shape

## Related documents

- `docs/IMPLEMENTATION_ALIGNMENT_AUDIT.md`
- `docs/IMPLEMENTATION_REFACTORING_PLAN.md`
- `docs/SCHEMA_EVOLUTION_PLAN.md`
- `docs/DATABASE_ARCHITECTURE.md`
- `docs/MASTER_ARCHITECTURE.md`


# ADR-013 — Phase 5C Multi-Tenant Completeness (Roles, Invites, Org Denormalization)

## Status

**Accepted** — approved by project owner, 31 July 2026.

## Context

DevGuard AI already ships organization-ready MVP tenancy (`organizations`, `organization_members`, `X-Organization-Id`). Phase 5C completes product multi-tenancy without rewriting auth or inventing parallel RBAC.

## Decision

1. **Roles:** Keep frozen v1.0 roles (`platform_admin`, `organization_owner`, `organization_admin`, `engineer`, `viewer`). Do not add `project_manager`. Document/UI may present `organization_admin` as covering Project Manager + Organization Administrator responsibilities for the MVP.
2. **Registration:** Keep automatic personal organization + `organization_owner` on register; redesign onboarding copy/UX as workspace/organization creation.
3. **Invitations:** Persist secure invitation tokens and accept/revoke/expiry flows; deliver via copyable link first. SMTP email is deferred.
4. **Denormalization:** Migration `010` adds `organization_id` to high-volume tenant rows (`incidents`, `incident_events`, `notifications`, `webhook_deliveries`) with backfill from existing join paths; `audit_logs.organization_id` already exists.
5. **GitHub:** Keep org-level `github_installations` and project-level `github_repository_connections`; Organization Settings surfaces org integrations (no duplicate credential store).
6. **Platform admin:** System Administration UI/APIs visible only to `platform_admin`; organization users see Organization Settings IA instead of a mixed Admin menu.

## Consequences

- Constitution role freeze preserved.
- Authorization and list queries can filter on `organization_id` directly while retaining project FKs.
- Invitation email infrastructure is not a Phase 5C dependency.
- Must not regress GitHub ingestion, AI analysis, or incident workflows.

## Related documents

- `docs/PHASE5C_ARCHITECTURE_AUDIT_AND_MIGRATION_PLAN.md`
- `docs/DATABASE_ARCHITECTURE.md`
- `docs/PROJECT_CONSTITUTION.md`
