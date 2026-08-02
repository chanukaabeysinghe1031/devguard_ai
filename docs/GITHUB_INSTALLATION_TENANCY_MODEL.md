# GitHub Installation Tenancy Model

## Principle

**Installation ID is not a tenant boundary.**  
**Organization membership + project + repository connection is.**

## Objects

| Object | Scope | Uniqueness |
|--------|-------|------------|
| `github_installations` | Global GitHub identity | `github_installation_id` unique |
| `github_installation_organization_access` | Org grant to use installation | `(installation_id, organization_id)` unique |
| `github_repository_connections` | Project watches a repo | Live: one per project; one per `(org, repo)` |
| Incidents / analyses / notifications | Organization (+ project) | Existing tenant FKs |

## Authorization checklist

Every GitHub-backed operation must confirm:

1. User belongs to the DevGuard organization.
2. Project belongs to that organization.
3. Repository connection belongs to that project and organization.
4. Organization has an ACTIVE access grant for the installation.
5. Installation status is usable (not deleted/suspended when action requires live GitHub).
6. Connection is active / not paused (for ingestion).
7. Requested GitHub repository id matches the connection.

Never authorize solely by guessing a numeric GitHub installation id. Setup requires a valid encrypted `state` (or equivalent provider-confirmed callback).

## Visibility rules

| Role | Can see |
|------|---------|
| Org owner/admin | Own org’s access grants, sync, link/unlink, connect repos |
| Engineer | Project connection + webhook/pipeline context per project rules |
| Viewer | Read-only integration metadata |
| Other orgs | Nothing about peer tenants using the same installation |

Do not expose names of other DevGuard organizations sharing an installation.
