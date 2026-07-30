# Phase 5B — GitHub App Setup

## Create the GitHub App

1. GitHub → Settings → Developer settings → GitHub Apps → New GitHub App
2. Name: `DevGuard AI` (or org-unique variant)
3. Homepage URL: your product URL
4. Webhook URL: `https://<public-host>/api/v1/integrations/github/webhook`
5. Webhook secret: generate a strong random value → `GITHUB_WEBHOOK_SECRET`
6. Permissions (Repository):
   - **Metadata**: Read-only
   - **Actions**: Read-only
7. Subscribe to events:
   - `workflow_run`
   - `installation`
   - `installation_repositories`
   - `ping` (optional)
8. Install on selected accounts/repos after creation
9. Generate private key → store as file mounted at `GITHUB_APP_PRIVATE_KEY_PATH`
10. Note App ID → `GITHUB_APP_ID`, slug → `GITHUB_APP_SLUG`

## Server configuration

Copy keys into `.env` from `.env.example` (never commit real values):

```env
GITHUB_APP_ENABLED=true
GITHUB_PROVIDER=github_app
GITHUB_APP_ID=...
GITHUB_APP_SLUG=...
GITHUB_APP_PRIVATE_KEY_PATH=/run/secrets/github_app.pem
GITHUB_WEBHOOK_SECRET=...
GITHUB_WEBHOOK_PUBLIC_URL=https://<public-host>/api/v1/integrations/github/webhook
INTEGRATION_ENCRYPTION_KEY=...  # Fernet key
```

## Product UI

Project → Integrations → GitHub Actions → Install DevGuard AI GitHub App → select repository → save automation settings → Test Connection.
