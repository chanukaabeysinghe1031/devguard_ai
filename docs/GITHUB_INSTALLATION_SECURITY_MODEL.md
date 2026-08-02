# GitHub Installation Security Model

## Shared installation ≠ shared tenant data

The GitHub App installation (and its short-lived installation token) may be shared.  
All DevGuard AI business data remains organization-scoped.

## Token rules

- Tokens minted server-side via existing `GitHubProvider` only.
- Never returned to the frontend.
- Never logged.
- Not persisted as plaintext installation access tokens.
- Before any GitHub API call for a project: verify org membership, ACTIVE access grant, and repository connection.

## Threat mitigations

| Threat | Control |
|--------|---------|
| Guess installation id | Encrypted setup `state` binds org; access grant required |
| Cross-org API read | `_load_installation` requires ACTIVE access for caller org |
| Webhook single-tenant race | Fan-out + per-connection ledger |
| Activity feed leak on shared repo | List by connection processing, not bare `repository_id` |
| Org A disconnect harms Org B | Disconnect deactivates only that org’s access/connections |
| Org delete CASCADE kills shared install | Installation `organization_id` FK is SET NULL (legacy); access rows CASCADE per org |

## Observability (safe fields)

Log: installation internal id, GitHub installation id, organization id, project id, repository connection id, GitHub repository id, webhook delivery id, fan-out count.

Never log: installation tokens, private keys, webhook secrets, raw sensitive repo contents.
