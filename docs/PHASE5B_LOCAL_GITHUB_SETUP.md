# Phase 5B — Local GitHub Setup

## Preferred for this smoke — Real App + tunnel (no fake mode)

1. Expose local backend with HTTPS (ngrok, Cloudflare Tunnel, etc.).
2. Set GitHub App webhook URL to `https://<tunnel>/api/v1/integrations/github/webhook`.
3. Place App private key at `.secrets/github-app.pem` (Compose mounts it read-only to `/run/secrets/github-app.pem`).
4. Set `.env` from `.env.example` with `GITHUB_PROVIDER=github` (not `fake`).
5. Install the App on a disposable test repository via Project → Integrations.
6. Map the repository, enable automation, run **Test Connection**.
7. Only after Test Connection passes: push a failing workflow and confirm incident + analysis.

### Exact local URLs

| Purpose | URL |
|--------|-----|
| Homepage | `http://localhost:5173` |
| Setup URL (GitHub App setting) | `http://localhost:5173/integrations/github/setup` |
| Webhook URL | `https://<tunnel>/api/v1/integrations/github/webhook` |
| Health check via tunnel | `https://<tunnel>/api/v1/health` |

Setup URL redirects the browser after install — localhost is fine on the same machine. Webhooks require the public tunnel.

### Copy webhook secret into GitHub (do not paste into chat)

```bash
# macOS
grep '^GITHUB_WEBHOOK_SECRET=' .env | cut -d= -f2- | pbcopy
```

## Optional — Fake provider (CI / unit tests only)

```env
GITHUB_APP_ENABLED=true
GITHUB_PROVIDER=fake
GITHUB_WEBHOOK_SECRET=test-webhook-secret
INTEGRATION_ENCRYPTION_KEY=<fernet-key>
```

Use pytest (`tests/test_github_ingestion_api.py`). Production rejects `fake`.

## Replay helper

For signature tests, HMAC-SHA256 the **exact raw body** with the webhook secret and set `X-Hub-Signature-256: sha256=<hex>`.

Production must never accept unsigned webhooks.
