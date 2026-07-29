# Implementation Refactoring Plan

**Project:** DevGuard AI  
**Date:** 23 July 2026  
**Depends on:** `docs/IMPLEMENTATION_ALIGNMENT_AUDIT.md`  
**Status:** Awaiting approval — **do not implement until approved**

---

## Guiding Principles

1. **Do not rewrite the project.** Evolve what exists.  
2. **Do not delete the database.** Prefer additive Alembic migrations.  
3. **Do not discard the 11 existing tables.** Evolve them per DATABASE_ARCHITECTURE §9.  
4. **Do not start auth/API/AI features** until schema alignment decisions are approved.  
5. **MASTER_ARCHITECTURE + DATABASE_ARCHITECTURE win** over older Module 2 assumptions and Cursor Module 1 lock.  
6. One change stream at a time: docs/rules → schema plan → migrations → repos → services → APIs → frontend.

---

## Priority Legend

| Priority | Meaning |
|----------|---------|
| **Critical** | Blocks correct architecture; must resolve before further domain work |
| **High** | Required soon after Critical; high risk if delayed |
| **Medium** | Important for quality/compliance; can follow Critical/High |
| **Low** | Polish, deferred, or phase-later items |

Effort estimates are relative engineer-days for a single experienced developer.

---

## Issue Register

### R-001 — Cursor rules and process lock are outdated

| Field | Value |
|-------|-------|
| Priority | **Critical** |
| Effort | 0.5 day |
| Risk | Low |
| Affected files | `.cursor/rules/devguard-ai.mdc`, possibly `README.md` |
| Problem | Rules still mandate Module 1 only and reference deleted `SYSTEM_ARCHITECTURE.md`. Agents and humans follow wrong constraints. |
| Recommended solution | Update authority document list to the frozen 10-doc set. Set current module to **Module 2 — Schema Evolution (alignment)**. Remove SYSTEM_ARCHITECTURE reference; point to MASTER_ARCHITECTURE. Keep “no future modules early” but allow schema alignment work. |

---

### R-002 — Implemented schema diverges from DATABASE_ARCHITECTURE

| Field | Value |
|-------|-------|
| Priority | **Critical** |
| Effort | 5–8 days (design + migrations + model updates + tests) |
| Risk | **High** (data model change; migration ordering) |
| Affected files | `backend/app/infrastructure/database/models/*`, `backend/alembic/versions/*`, `backend/app/domain/enums.py`, `backend/app/infrastructure/database/enums.py`, repositories, seed, repository tests |
| Problem | Current 11-table flat ML schema lacks organizations, projects, incidents, analysis_runs; wrong FKs; premature `analysis_history`; naming mismatches (`hashed_password` vs `password_hash`, `slug` vs `code`, enum values). |
| Recommended solution | Produce an ADR describing Migration 002–004 plan matching DATABASE_ARCHITECTURE §10. Keep existing tables; add new core tables; alter columns/FKs; stop treating `001_initial_schema` as final. **Do not generate migrations until ADR approved.** |

#### Suggested migration waves (design only)

| Wave | Intent |
|------|--------|
| **002** | Create `organizations`, `organization_members`, `projects`, `project_integrations`; extend `users` (`password_hash` rename/alias strategy, `avatar_url`, `last_login_at`, role values) |
| **003** | Create `incidents`, `analysis_runs`; extend `pipeline_runs` toward project ownership; extend `uploaded_files` with project/incident/run FKs and status fields |
| **004** | Relink `predictions`, `evidence_items`, `recommendations`, `feedback` to `analysis_run_id` / incident; deprecate/drop `analysis_history` for MVP; add `audit_logs` foundation |

---

### R-003 — `analysis_history` table should not exist for MVP

| Field | Value |
|-------|-------|
| Priority | **Critical** (schema correctness) |
| Effort | 0.5–1 day (within R-002) |
| Risk | Medium (if any code depends on it — currently seed/repos do not heavily use it) |
| Affected files | `models/analysis_history.py`, Alembic 001 (historical), future migration, model `__init__.py` |
| Problem | DATABASE_ARCHITECTURE §5.26: do not create for MVP; derive history from incidents/analysis_runs. |
| Recommended solution | Plan a later migration to drop or freeze the table. Do not build repositories/APIs against it. Document as deprecated immediately in ADR. |

---

### R-004 — Enum and naming inconsistencies

| Field | Value |
|-------|-------|
| Priority | **High** |
| Effort | 1–2 days |
| Risk | Medium |
| Affected files | `domain/enums.py`, `infrastructure/database/enums.py`, models, seed, Alembic |
| Problem | Role `analyst` vs `engineer`; pipeline statuses differ; failure category `slug` vs `code`; password column naming; file types incomplete vs DB doc. |
| Recommended solution | Publish a single **Canonical Enum ADR** from MASTER + DATABASE. Migrate PostgreSQL enums carefully (`ALTER TYPE` / recreate strategy). Prefer additive enum values where possible. |

---

### R-005 — Failure category taxonomy conflict

| Field | Value |
|-------|-------|
| Priority | **High** |
| Effort | 1 day |
| Risk | Medium (seed + ML labels) |
| Affected files | `seed.py`, DATASET_SPECIFICATION, DATABASE_ARCHITECTURE examples |
| Problem | Seeded 11 categories match older MSc list; DATABASE_ARCHITECTURE lists a broader/different example set (`authentication_failure`, `terraform_plan_failure`, etc.). |
| Recommended solution | Decide one MVP taxonomy in an ADR (recommend keep current 11 for MSc continuity, map aliases later). Update DATABASE_ARCHITECTURE examples or seed docs so they no longer conflict. |

---

### R-006 — Repository layer incomplete / wrong anchors

| Field | Value |
|-------|-------|
| Priority | **High** |
| Effort | 3–4 days (after schema) |
| Risk | Medium |
| Affected files | `domain/interfaces/repositories.py`, `infrastructure/repositories/*`, `domain/entities/*`, `tests/test_repositories.py` |
| Problem | Only User / FailureCategory / PipelineRun repos. PipelineRun is user-scoped, not project-scoped. Missing Project/Incident/AnalysisRun repositories required by architecture. |
| Recommended solution | After R-002, add repository interfaces/implementations for Organization, Project, Incident, AnalysisRun, UploadedFile. Update PipelineRunRepository to project-centric queries. Keep flush-not-commit transaction rule. |

---

### R-007 — Empty application and schema layers

| Field | Value |
|-------|-------|
| Priority | **High** |
| Effort | 2–3 days (initial scaffolding after auth schema) |
| Risk | Low |
| Affected files | `backend/app/services/` (empty), `backend/app/schemas/` (empty), preferably rename/move to `application/services/` and `api` schemas per PROJECT_STRUCTURE |
| Problem | Clean Architecture requires application services; empty folders invite route-level logic later. |
| Recommended solution | Introduce `application/services/` package; put Pydantic DTOs next to API or under `schemas/` consistently. First services: Auth, Organization bootstrap, Project. |

---

### R-008 — Health API path / live probe mismatch

| Field | Value |
|-------|-------|
| Priority | **Medium** |
| Effort | 0.5 day |
| Risk | Low |
| Affected files | `api/v1/endpoints/health.py`, API_SPECIFICATION.md, frontend `api/health.ts`, tests |
| Problem | Spec shows `/health`, `/health/ready`, `/health/live`; code has `/api/v1/health` and `/api/v1/health/ready` only. |
| Recommended solution | Standardize on `/api/v1/health`, `/api/v1/health/ready`, `/api/v1/health/live`. Update API_SPECIFICATION to match (MASTER prefers `/api/v1`). |

---

### R-009 — Backend package naming vs PROJECT_STRUCTURE

| Field | Value |
|-------|-------|
| Priority | **Medium** |
| Effort | 1 day |
| Risk | Medium (imports) |
| Affected files | `api/v1/endpoints/` → preferred `routes/`; missing `core/security.py`, `utils/` |
| Problem | Structure diverges from PROJECT_STRUCTURE naming. |
| Recommended solution | Gradual rename after tests green; avoid big-bang move. Add `core/security.py` only when Auth module starts. |

---

### R-010 — Frontend shell far below SCREEN_SPECIFICATION

| Field | Value |
|-------|-------|
| Priority | **Medium** (defer until APIs exist) |
| Effort | 10–20 days for MVP screens (later phase) |
| Risk | Low if deferred correctly |
| Affected files | `frontend/src/**` |
| Problem | Only HomePage + health badge. Missing layout, auth, dashboard, projects, incidents, upload, etc. |
| Recommended solution | Do not build full UI now. When Phase 7 starts: scaffold layout + auth pages first, then projects/incidents. Follow SCREEN_SPECIFICATION strictly. |

---

### R-011 — Docker healthchecks and observability gaps

| Field | Value |
|-------|-------|
| Priority | **Medium** |
| Effort | 0.5 day |
| Risk | Low |
| Affected files | `docker-compose.yml`, Dockerfiles |
| Problem | Postgres has healthcheck; backend/frontend do not. |
| Recommended solution | Add backend curl healthcheck to `/api/v1/health`; optional frontend check later. |

---

### R-012 — Test suite skipped without Postgres / missing coverage

| Field | Value |
|-------|-------|
| Priority | **High** |
| Effort | 1–2 days |
| Risk | Medium |
| Affected files | `tests/conftest_db.py`, CI config (missing), future migration tests |
| Problem | 21 DB tests skipped when Docker/Postgres unavailable. No CI workflow. No migration round-trip test automated. |
| Recommended solution | Document required `docker compose up -d postgres` for DB tests. Add GitHub Actions later (Roadmap deploy phase can come earlier for CI-only). Add alembic upgrade/downgrade job after R-002. |

---

### R-013 — Documentation drift and missing ADR process

| Field | Value |
|-------|-------|
| Priority | **High** |
| Effort | 1 day |
| Risk | Low |
| Affected files | `README.md`, `PROJECT_STRUCTURE.md`, new `docs/ADR/` (optional), Cursor rules |
| Problem | README Module 2 status incomplete; PROJECT_STRUCTURE lags MASTER; no ADR for schema evolution. |
| Recommended solution | Update README current status to “Module 2 — schema alignment required”. Add ADR-001 Schema Evolution. Soft-update PROJECT_STRUCTURE org/incident folders. |

---

### R-014 — Top-level folder gaps (`datasets`, `knowledge_base`, `.github`)

| Field | Value |
|-------|-------|
| Priority | **Low** |
| Effort | 0.5 day |
| Risk | Low |
| Affected files | repo root |
| Problem | PROJECT_STRUCTURE expects datasets/knowledge_base/scripts/.github; placeholders use `dataset/` and `data/`. |
| Recommended solution | Align folder names when Dataset/RAG modules start; avoid premature empty sprawl. |

---

### R-015 — AI module entirely absent

| Field | Value |
|-------|-------|
| Priority | **Low** (correctly deferred) |
| Effort | Large (later phases) |
| Risk | N/A now |
| Affected files | future `backend/app/ai/**`, Compose ChromaDB |
| Problem | 0% AI implementation vs AI_ARCHITECTURE. |
| Recommended solution | Do not scaffold AI packages until upload + analysis_runs + dataset pipeline exist. |

---

### R-016 — Orphan bytecode / empty package hygiene

| Field | Value |
|-------|-------|
| Priority | **Low** |
| Effort | 0.25 day |
| Risk | Low |
| Affected files | `__pycache__`, empty `services/`, `schemas/` |
| Problem | Possible orphan `.pyc` without source; empty packages unclear. |
| Recommended solution | Confirm no missing source; clean cache; either implement packages or document them as reserved. |

---

## Recommended Execution Order (After Approval)

```text
1. R-001  Update Cursor rules + README status
2. R-013  ADR-001 Schema Evolution + doc soft sync
3. R-005  Taxonomy ADR (keep 11 categories unless overruled)
4. R-004  Canonical enums ADR
5. R-002  Schema evolution migrations (002–004) + model updates
6. R-003  Deprecate/drop analysis_history in same wave
7. R-012  Re-enable/verify all DB tests + add migration tests
8. R-006  Expand repositories for new entities
9. R-008  Health endpoint standardization
10. R-011 Docker healthchecks
11. R-007 Application services scaffolding (Auth next module)
12. R-009 Gradual package rename
13. R-010 Frontend (only after auth/projects APIs)
14. R-014 / R-015 / R-016 as needed later
```

---

## Explicit Non-Goals (Until Further Approval)

- Generating Alembic migrations in this phase  
- Implementing authentication  
- Implementing upload/incident APIs  
- Scaffolding AI/RAG/LLM code  
- Rewriting frontend to full SaaS UI  
- Deleting PostgreSQL volumes or Module 1 foundation code  
- Big-bang rewrite of repositories  

---

## Risk Summary

| Risk | Mitigation |
|------|------------|
| Migrating live local DB breaks data | Prefer additive migrations; document `downgrade` warning; use `devguard_test` for validation |
| Continuing Module 2 as-is locks wrong model | Freeze feature work until R-002 approved |
| Enum rename breaks seed | Keep slug/code dual-write briefly if needed |
| Doc conflicts (roles, taxonomy) | ADRs + MASTER authority |

---

## Approval Gate

Please review:

1. `docs/IMPLEMENTATION_ALIGNMENT_AUDIT.md`  
2. This refactoring plan  

Approve explicitly which items may proceed (recommend starting with **R-001 + R-013 + ADR for R-002** only).

**No implementation will start until you approve.**
