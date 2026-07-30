# Phase 5B — Implementation Audit

**Date:** 2026-07-30  
**Branch:** `feature/enterprise-incident-management-ui`  
**Baseline:** Phase 5A / `v1.0.0-rc2`  
**Authority:** MASTER_ARCHITECTURE → PROJECT_CONSTITUTION → DATABASE_ARCHITECTURE → API_SPECIFICATION → AI_ARCHITECTURE → screen/workflow specs → IMPLEMENTATION_ROADMAP → Phase 4/5A docs

---

## 1. Documents reviewed

| Document | Finding relevant to 5B |
|----------|------------------------|
| MASTER_ARCHITECTURE | Automated webhook ingestion listed as future; GitHub Actions first CI |
| PROJECT_CONSTITUTION | Observe/diagnose/recommend — no self-heal; no PAT in UI |
| DATABASE_ARCHITECTURE | `project_integrations` schema-ahead; incident `source` includes `webhook` |
| API_SPECIFICATION §28 | Future `POST /webhooks/github` — not implemented |
| AI_ARCHITECTURE | Same parsers for Actions logs; webhook ingestion deferred |
| SCREEN_SPECIFICATION | Integrations screens planned |
| IMPLEMENTATION_ROADMAP | Module 3.2 integrations; duplicate external_run_id prevention noted |
| Phase 5A docs | Manual workflow complete; notifications + analysis orchestration reusable |

---

## 2. Existing components to reuse

| Component | Status | Phase 5B use |
|-----------|--------|--------------|
| `projects` / org membership | Ready | Map repo → project |
| `project_integrations` | Schema only (no API) | Optional metadata companion; GitHub App uses dedicated tables |
| `pipeline_runs` | Ready (no unique on external_run_id) | Upsert failed workflow runs |
| `incidents` + lifecycle | Ready | Auto-create with `source=github_webhook` |
| `uploaded_files` + storage + secret mask | Ready | Persist downloaded logs (`user_id` gap) |
| Analysis orchestration | Ready | Queue after ingestion |
| `NotificationService` | Ready | Fan-out; add `incident_created` helper |
| `incident_events` | Ready | System actor timeline |
| FastAPI `BackgroundTasks` + `ANALYSIS_EXECUTION_MODE` | Ready | Async webhook processing (no Celery) |

---

## 3. Gap matrix

| Capability | Exists | Gap | Decision |
|------------|--------|-----|----------|
| GitHub App JWT / installation token | No | Provider | Build `GitHubAppProvider` + `FakeGitHubProvider` |
| Webhook signature endpoint | No | Route + raw body | `POST /api/v1/integrations/github/webhook` |
| Delivery idempotency store | No | Table | `webhook_deliveries` UNIQUE `(provider, delivery_id)` |
| Org-level installation | No | Table | `github_installations` |
| Repo → project mapping + automation flags | Partial JSON on `project_integrations` | First-class | `github_repository_connections` |
| Pipeline run uniqueness | Index only | Constraint | UNIQUE `(project_id, provider, external_run_id, run_attempt)` via metadata/attempt |
| Credential encryption | Column only | Fernet | Env `INTEGRATION_ENCRYPTION_KEY`; encrypt setup state; never store installation tokens long-term |
| System uploader for files | `user_id` NOT NULL | Allow nullable OR platform service user | Prefer nullable `user_id` for system ingestion |
| Integration UI | No | Frontend | Project Integrations routes |
| Background worker process | BackgroundTasks only | Durable delivery status + retries on delivery rows | DB-backed status machine; process via BackgroundTasks / sync for tests |

---

## 4. Migration requirement

**Yes — Alembic `009_github_ingestion.py`:**

1. `github_installations`
2. `github_repository_connections`
3. `webhook_deliveries`
4. Unique index on `pipeline_runs (project_id, provider, external_run_id)` where external_run_id IS NOT NULL (attempt stored in `raw_metadata.run_attempt`)
5. `uploaded_files.user_id` → nullable (system ingestion)
6. Optional: extend `project_integrations` status values with `paused` via app-level status on connection table (use connection `is_active` + `paused_at` instead of altering enum)

---

## 5. Job-processing decision

**Chosen:** PostgreSQL-backed `webhook_deliveries.processing_status` + FastAPI `BackgroundTasks` (and sync path for tests).

**Rejected for this phase:** Celery/Redis/Kafka (infrastructure not justified for MSc modular monolith).

Durable state lives on `webhook_deliveries`; retries update `attempt_count` / `next_attempt_at`. Worker recovery: on startup, reclaim `queued`/`retrying` rows older than threshold (optional follow-up).

---

## 6. Security gaps to close

- HMAC-SHA256 raw-body validation
- Signed OAuth-style setup `state` (user/org/project/nonce/expiry)
- Archive bomb / path traversal limits on log ZIP
- No private key / webhook secret in API or frontend
- Tenant isolation on installation ↔ organization

---

## 7. UI gaps

- `/projects/:id/integrations` (+ `/github`)
- Setup callback `/integrations/github/setup`
- Incident source badge + GitHub context strip
- Dashboard metrics only if queryable

---

## 8. Audit conclusion

Proceed with **ADR-005**: GitHub App + new installation/connection/delivery tables + reuse analysis/notifications; manual upload remains.

**Module 5B.1 complete — proceed to provider foundation and migrations.**
