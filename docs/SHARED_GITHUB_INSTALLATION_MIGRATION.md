# Shared GitHub Installation Migration

**Revision:** `019_shared_github_installations`  
**Parent:** `018_phase6a6_verifiers`

## Upgrade steps

1. Create `github_installation_organization_access`.
2. Backfill one ACTIVE grant per existing installation with `organization_id`.
3. Add nullable `installation_access_id` on `github_repository_connections`.
4. Backfill access ids by `(installation_id, organization_id)`.
5. Create `webhook_delivery_connection_processing`.
6. Make `github_installations.organization_id` nullable; FK `ON DELETE SET NULL`.
7. Preserve all installations, connections, deliveries, incidents, analyses.

## Constraints

| Kept | Changed / added |
|------|-----------------|
| `uq_github_installations_github_installation_id` | Access unique `(installation_id, organization_id)` |
| `uq_webhook_deliveries_provider_id` | Processing unique `(webhook_delivery_id, repository_connection_id)` |
| Project-scoped pipeline run unique | Installation org column demoted (nullable legacy) |
| Live connection per project / per (org, repo) | — |

## Downgrade

Drops new tables/columns; best-effort restore of a primary `organization_id` from the earliest ACTIVE access grant. Installations that gained multiple orgs after upgrade may remain nullable and cannot be forced NOT NULL.

## Apply

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
```

Do not run `docker compose down -v`.
