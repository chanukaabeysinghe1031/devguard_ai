# Configuration Audit — Phase 4B

**Date:** 2026-07-29  
**Sources:** `backend/app/core/config.py`, `.env.example`, Compose env.

## Summary

| Check | Result |
|-------|--------|
| Settings fields missing from `.env.example` | None |
| `.env.example` keys outside Settings | Intentional: `FRONTEND_PORT`, `VITE_API_BASE_URL`, `GITHUB_TOKEN`, OpenAI cost aliases |
| Production startup validation | `Settings.validate_for_runtime()` + raise in `get_settings()` when `ENVIRONMENT=production` |
| OpenAI required for local fallback | No — local reasoner remains available |

## Alias notes

- `OPENAI_INPUT_COST_PER_1M_TOKENS` / `OPENAI_OUTPUT_COST_PER_1M_TOKENS` map to the same fields as `LLM_INPUT_COST_USD_PER_MILLION_TOKENS` / `LLM_OUTPUT_COST_USD_PER_MILLION_TOKENS`.
- Compose overrides `CHROMA_HOST=chroma` inside the backend service.

## Unsafe development defaults (intentional for local demo)

| Setting | Dev default / example | Production requirement |
|---------|----------------------|-------------------------|
| `POSTGRES_PASSWORD` | `change_me` | Must change |
| `JWT_SECRET_KEY` | placeholder ≥32 chars | Strong unique secret |
| `DEBUG` | `true` in example | Must be `false` |
| `BOOTSTRAP_ENABLED` | false by default | Must stay false |
| `ENABLE_RAG` / `ENABLE_LLM` | true in example; false in code defaults | Explicit ops choice |
| Backend/Frontend Docker CMD | reload / Vite dev | Prod images deferred |

## Critical validation rules (production)

Reject / fail startup when:

- JWT secret shorter than 32 characters
- Debug or bootstrap enabled
- Empty CORS origins
- Development DB password
- External OpenAI enabled without API key
- Invalid upload size, retry, timeout, or negative cost values
- Chroma selected without host/persist path

## Applicable environments

| Variable class | Local Compose | Staging | Production |
|----------------|---------------|---------|------------|
| Postgres / JWT / CORS | required | required | required + hardened |
| Chroma + embeddings | recommended | recommended | required if RAG on |
| OpenAI | optional | optional | optional |
| Federated secondary collection | optional | optional | optional |
| Vite API base | required for UI | required | build-time |
