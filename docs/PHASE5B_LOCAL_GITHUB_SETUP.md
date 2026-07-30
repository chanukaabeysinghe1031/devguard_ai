# Phase 5B — Local GitHub Setup

## Option A — Fake provider (deterministic)

```env
GITHUB_APP_ENABLED=true
GITHUB_PROVIDER=fake
GITHUB_WEBHOOK_SECRET=test-webhook-secret
INTEGRATION_ENCRYPTION_KEY=<fernet-key>
```

Use pytest suite (`tests/test_github_ingestion_api.py`) for full ingest flow. Do **not** use `fake` in production (`ENVIRONMENT=production` rejects it).

## Option B — Real App + tunnel

1. Expose local backend with HTTPS (Cloudflare Tunnel, ngrok, etc.) — do not hard-code a vendor into architecture.
2. Set GitHub App webhook URL to the tunnel URL + `/api/v1/integrations/github/webhook`.
3. Mount the private key read-only into the backend container.
4. Install the App on a disposable test repository.
5. Push a failing workflow; confirm incident appears in DevGuard UI.

## Replay helper

For signature tests, HMAC-SHA256 the **exact raw body** with the webhook secret and set `X-Hub-Signature-256: sha256=<hex>`.

Production must never accept unsigned webhooks.
