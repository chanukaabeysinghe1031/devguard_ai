# Phase 5C — Role Matrix (ADR-013)

Frozen organization roles are unchanged. UI labels may present `organization_admin` as covering **Project Manager + Organization Administrator** responsibilities for the MVP.

| Capability | Owner | Admin | Engineer | Viewer | Platform admin |
|------------|-------|-------|----------|--------|----------------|
| Org profile edit | ✓ | ✓ | | | System only |
| Invite / revoke members | ✓ | ✓ | | | — |
| Configure GitHub | ✓ | ✓ | | | — |
| Create projects | ✓ | ✓ | ✓ | | — |
| Create incidents / upload / AI | ✓ | ✓ | ✓ | | — |
| Resolve incidents | ✓ | ✓ | ✓ | | — |
| Read dashboards / incidents | ✓ | ✓ | ✓ | ✓ | — |
| System Health / Models / Audit | | | | | ✓ only |

**Platform admin** uses `users.platform_role = platform_admin` and the **System** nav. It does not silently unlock Organization menu items via `hasAnyRole`.

**Invitations:** secure copyable links; SMTP deferred.
