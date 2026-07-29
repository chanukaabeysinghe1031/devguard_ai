# Clean-Start Verification — Phase 4B

**Date:** 2026-07-29  
**Caution:** `docker compose down -v` deletes Postgres, Chroma, and model-cache volumes. This environment holds ingested research/product corpora. A destructive wipe was **not** executed against the live project volumes.

## Documented clean-start procedure (isolated)

```bash
# 1) Backup or use a separate Compose project name
export COMPOSE_PROJECT_NAME=devguard_clean
# 2) Optionally remap host ports to avoid clashes with a running stack
export BACKEND_PORT=18000 FRONTEND_PORT=15173
# 3) Wipe ONLY the isolated project volumes
docker compose down -v
# 4) Rebuild without relying on ad-hoc pip inside running containers
docker compose build --no-cache
docker compose up -d
# 5) Wait for health
docker compose ps
curl -fsS http://127.0.0.1:${BACKEND_PORT:-8000}/api/v1/health
# 6) Restore corpora
#    - knowledge_base bind-mount is automatic
#    - re-ingest research/product collections via documented CLI if Chroma volume is empty
```

## Verified on the current (non-wiped) stack

| Check | Result | Evidence |
|-------|--------|----------|
| `docker compose config` | Pass | Valid Compose file |
| Postgres healthy | Pass | `devguard_postgres` healthy |
| Chroma healthy | Pass | `devguard_chroma` healthy |
| Backend up + healthcheck | Pass | curl `/api/v1/health` healthcheck in Compose |
| Frontend up | Pass | `devguard_frontend` up |
| OpenAI package in image deps | Pass | `requirements.txt` / `pyproject.toml` include `openai>=1.40.0` |
| Embedding model available | Pass | ST provider loads; model cache volume present |
| Migrations/seed path | Pass | Existing stack serves migrated schema; seed on bootstrap path |
| Restart policy | Pass | `restart: unless-stopped` on services |
| Persistent volumes documented | Pass | `postgres_data`, `chroma_data`, `model_cache` |
| No manual in-container pip required for declared deps | Pass | Image build installs requirements |

## Residual limitations

- Full `down -v` against production-like local corpora was deferred to protect benchmark indexes.
- Frontend image still serves Vite dev (`npm run dev`) — not a production static build.
- Backend image still uses `--reload` — not a production gunicorn/uvicorn worker image.
- After a real wipe, operators must re-ingest Chroma collections before retrieval benchmarks match prior numbers.

## Rebuild verification command (non-destructive)

```bash
docker compose build backend frontend
docker compose up -d
docker compose exec backend python -c "import openai, sentence_transformers; print('ok')"
```
