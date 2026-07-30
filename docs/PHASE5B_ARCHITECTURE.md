# Phase 5B — Architecture

**Amendment to:** MASTER_ARCHITECTURE v1.0 (GitHub Actions automated ingestion)  
**ADR:** ADR-005

## Dual ingestion paths

```text
Manual:  User → Upload → Incident → Analysis → Notify
GitHub:  workflow_run.completed → Webhook → Delivery → Ingest → Incident → Analysis → Notify
```

Both converge on the same domain models and AI orchestration.

## Component map

| Layer | Components |
|-------|------------|
| API | `integrations/github/*` (JWT) + `integrations/github/webhook` (HMAC) |
| Application | `GitHubSetupService`, `GitHubIngestionService`, `WebhookDeliveryService` |
| Domain/providers | `GitHubProvider` protocol; `GitHubAppProvider`; `FakeGitHubProvider` |
| Infrastructure | ORM models; Fernet state crypto; ZIP log extractor |
| Jobs | Delivery status machine + BackgroundTasks |
| Frontend | Project Integrations + incident GitHub badges |

## Event flow (happy path)

1. Validate HMAC + headers; persist `webhook_deliveries` (unique delivery_id).
2. Enqueue processing; return 202/200 quickly.
3. Resolve installation → connection → project; apply workflow/branch/conclusion filters.
4. Upsert `pipeline_runs`; download logs; extract safely; mask secrets; store files.
5. Create incident (`source=github_webhook`); timeline system events; start analysis.
6. Notifications (idempotent keys in metadata).

## Security boundaries

- Webhook: signature required in production; optional `GITHUB_WEBHOOK_DEV_UNSIGNED=false` never enables unsigned in production environment.
- Tokens: never in logs, API responses, or frontend env.
- Archives: size/file/path/symlink limits.
