# ADR-005 — Automated GitHub Actions Incident Ingestion

**Status:** Accepted  
**Date:** 2026-07-30  
**Phase:** 5B  
**Supersedes:** None (extends v1.0 input scope with versioned amendment)

## Context

Phase 5A delivers a complete **manual** incident workflow. The approved product vision includes automated detection of CI failures. GitHub Actions is the first CI provider in MASTER_ARCHITECTURE and DATABASE_ARCHITECTURE.

## Decision

1. **GitHub Actions first** — Terraform, Maven, Docker, npm, etc. appear *inside* Actions logs; the existing AI pipeline classifies them. No separate webhooks per technology in Phase 5B.
2. **GitHub App** — preferred over PATs pasted into the UI. Installation tokens are short-lived and created on demand. Private key and webhook secret live only in server environment / mounted files.
3. **Manual upload remains** — second ingestion path; never removed or gated behind GitHub.
4. **Minimum permissions** — Repository Metadata: Read; Actions: Read. No write permissions.
5. **Background processing** — durable `webhook_deliveries` row + FastAPI BackgroundTasks (tests use sync). No Celery in Phase 5B.
6. **Credential storage** — no installation access tokens persisted. Setup `state` and any future secret references use Fernet with `INTEGRATION_ENCRYPTION_KEY`. Webhook secret and App private key are env/file only.
7. **Schema** — add `github_installations`, `github_repository_connections`, `webhook_deliveries` rather than overloading `project_integrations` alone (org-level App install ≠ project row).
8. **Failure/retry** — retriable GitHub/network errors increment attempts; permanent errors mark delivery failed; duplicates by `X-GitHub-Delivery` and by `(project, provider, external_run_id)` do not create duplicate incidents/analyses.
9. **No self-healing** — observe, diagnose, recommend only. Never rerun workflows or mutate repos.
10. **Deferred providers** — GitLab, Jenkins, Azure DevOps, Terraform Cloud, EventBridge shown as “Coming later” without Connect actions.

## Consequences

- New public webhook route (signature auth, not JWT).
- New Alembic migration `009`.
- New Integrations UI under Project Details.
- Architecture scope amendment: automated ingestion is now in-scope for GitHub Actions only.

## Alternatives considered

| Alternative | Why rejected |
|-------------|--------------|
| Long-lived PAT in UI | Security / constitution |
| Celery + Redis | Extra infra for MSc MVP |
| Only extend `project_integrations` | Weak org-level installation model |
| Per-technology webhooks | Duplicate plumbing; logs already contain tech signals |
