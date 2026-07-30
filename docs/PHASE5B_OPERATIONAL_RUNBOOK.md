# Phase 5B — Operational Runbook

## Enable

1. Configure GitHub App (setup doc).
2. Set env vars; mount private key.
3. `GITHUB_APP_ENABLED=true`, restart backend.
4. Run migration `009` if not applied.
5. Connect via Project → Integrations.

## Disable

Set `GITHUB_APP_ENABLED=false` or Pause Automation / Disconnect in UI. Historical incidents remain.

## Common failures

| Symptom | Action |
|---------|--------|
| Invalid signature | Check `GITHUB_WEBHOOK_SECRET` matches App |
| Events ignored | Check filters / paused / wrong repo mapping |
| Logs missing | Check Actions: Read permission; log retention |
| Analysis not started | `auto_start_analysis`; check analysis worker/mode |
| Rate limited | Retrying status; wait for GitHub reset |

## Idempotency

Redeployed webhooks reuse `webhook_deliveries.delivery_id` and pipeline unique external_run_id — safe to replay.
