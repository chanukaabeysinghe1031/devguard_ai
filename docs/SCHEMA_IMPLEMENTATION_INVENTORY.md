# Schema Implementation — Pre-Migration Inventory (Step 2)

**Date:** 24 July 2026  
**Purpose:** Record mismatches found before implementing models/migrations (historical checklist).

## Inventory at start of approved schema phase

| Asset | Finding |
|-------|---------|
| Alembic head | `001_initial_schema` only |
| ORM tables | 11 legacy tables |
| Enums | `user_role` included `analyst`; pipeline statuses `pending/processing/...` |
| Repositories | User / FailureCategory / PipelineRun against legacy fields |
| Seed | Matched categories by `slug` |
| Fixtures | Truncated only `failure_categories` (+ later expanded) |
| `analysis_history` | Present in 001 — conflicts with DATABASE_ARCHITECTURE MVP guidance |

## Plan vs repository mismatches (resolved by this phase)

| Mismatch | Resolution |
|----------|------------|
| No organizations/projects/incidents/analysis_runs | Added in models + migrations 002–004 |
| `hashed_password` / `analyst` | → `password_hash` / `platform_role`; org roles on `organization_members` |
| `slug` on failure_categories | → `code` (same 11 values) |
| Predictions parented by `pipeline_runs` | → `analysis_runs` |
| Monolithic recommendation JSON | → `recommendations` + `recommendation_steps` |
| `analysis_history` | Dropped in migration 007 |
| Missing `project_integrations` | Added in 002 (reference-only secrets) |

## Post-implementation

- Models: **27** tables on `Base.metadata`
- Migrations: `001`…`007` chain
- Seeds: categories by `code` + optional bootstrap
- Tests: health + migrations + repositories + schema invariants + seed (DB tests require Postgres)
