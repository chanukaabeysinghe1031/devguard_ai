# Phase 5B — GitHub App Setup

Use the **real** GitHub provider only (`GITHUB_PROVIDER=github`). Do not use fake mode for local smoke testing against GitHub.

## Create the GitHub App

1. GitHub → Settings → Developer settings → GitHub Apps → New GitHub App
2. Name: globally unique (e.g. `DevGuard AI Chanuka`) — note the resulting **App slug**
3. Homepage URL (local): `http://localhost:5173`
4. **Do not** enable “Request user authorization (OAuth) during installation”
5. Setup URL (local browser redirect): `http://localhost:5173/integrations/github/setup`  
   Enable **Redirect on update**
6. Webhook Active: enabled  
   Webhook URL: `https://<public-tunnel-host>/api/v1/integrations/github/webhook`  
   Webhook secret: same value as `GITHUB_WEBHOOK_SECRET` in `.env`  
   SSL verification: **Enable**
7. Repository permissions:
   - **Metadata**: Read-only
   - **Actions**: Read-only  
   Leave all other repository permissions at No access
8. Subscribe to events:
   - `workflow_run` (required)
   - `installation` (recommended)
   - `installation_repositories` (recommended)
9. Where can this GitHub App be installed? **Only on this account** (for local MSc testing)
10. Create App → record **App ID**, **Client ID** (optional), **App slug**
11. Private keys → Generate a private key → save as `.secrets/github-app.pem` (chmod 600; never commit)

## Public HTTPS tunnel (required for webhooks)

GitHub cannot POST to `localhost`. Keep a tunnel to the backend running for the whole test:

```bash
ngrok http 8000
# or: cloudflared tunnel --url http://localhost:8000
```

Test:

```bash
curl https://<tunnel-host>/api/v1/health
```

Webhook URL becomes:

`https://<tunnel-host>/api/v1/integrations/github/webhook`

If the tunnel URL changes, update the GitHub App webhook URL.

**Setup URL** redirects the **user’s browser**, so `http://localhost:5173/integrations/github/setup` is correct for same-machine local UI testing. Only the webhook needs a public HTTPS URL.

## Server configuration

Copy keys into uncommitted `.env` (never commit real values). Exact names from `.env.example`:

```env
GITHUB_APP_ENABLED=true
GITHUB_PROVIDER=github
GITHUB_APP_ID=...
GITHUB_APP_SLUG=...
GITHUB_APP_NAME=DevGuard AI
GITHUB_APP_PRIVATE_KEY_PATH=/run/secrets/github-app.pem
GITHUB_WEBHOOK_SECRET=...
GITHUB_SETUP_REDIRECT_URL=http://localhost:5173/integrations/github/setup
INTEGRATION_ENCRYPTION_KEY=...  # Fernet key; do not rotate casually
```

Compose mounts `.secrets/github-app.pem` → `/run/secrets/github-app.pem:ro`.

After updating `.env` / PEM:

```bash
docker compose up -d --build backend
docker compose exec backend sh -c \
  'test -r /run/secrets/github-app.pem && echo "Private key mounted and readable"'
```

## Product UI

Project → Integrations → GitHub Actions → Install DevGuard AI GitHub App → map repository → save automation settings → **Test Connection**.

Do not trigger a deliberate workflow failure until Test Connection passes.
