# Phase 5B — Database Changes

**Migration:** `009_github_ingestion.py`  
**Depends on:** `008_refresh_tokens`

## New tables

### github_installations
Org-scoped GitHub App installation metadata (no tokens).

### github_repository_connections
Maps installation + repository → project with automation flags and filter JSON.

### webhook_deliveries
Idempotent delivery ledger: UNIQUE `(provider, delivery_id)`.

## Altered tables

| Change | Reason |
|--------|--------|
| `uploaded_files.user_id` nullable | System/GitHub ingestion without a human uploader |
| Unique `(project_id, provider, external_run_id)` on `pipeline_runs` where `external_run_id IS NOT NULL` | Duplicate webhook protection |

## Retention

Store sanitised event snapshot JSON (ids, names, conclusions) — not full unredacted webhook bodies indefinitely. `payload_hash` for integrity.
