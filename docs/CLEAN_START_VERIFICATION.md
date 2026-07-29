# Clean-Start Verification — Phase 4B

**Date:** 2026-07-29  
**Caution:** Never run `docker compose down -v` against the live `devguard_ai` project while corpora exist. Use an isolated Compose project instead.

## Isolated clean-start (executed)

Files:

- `docker-compose.phase4-clean.yml` — separate ports/volumes/containers
- `.env.phase4-clean` — local-only secrets (gitignored)

```bash
# Backup live volumes first (see backups/phase4_*)
COMPOSE_PROJECT_NAME=devguard_phase4_clean \
  docker compose -f docker-compose.phase4-clean.yml --env-file .env.phase4-clean \
  up -d --build

# Migrations + seed categories
COMPOSE_PROJECT_NAME=devguard_phase4_clean \
  docker compose -f docker-compose.phase4-clean.yml --env-file .env.phase4-clean \
  exec backend alembic upgrade head
# then seed failure categories via seed_failure_categories()

# Tear down ONLY the isolated stack
COMPOSE_PROJECT_NAME=devguard_phase4_clean \
  docker compose -f docker-compose.phase4-clean.yml --env-file .env.phase4-clean \
  down -v
```

### Isolated verification results

| Check | Result |
|-------|--------|
| Live stack untouched | Pass (`devguard_*` still healthy on :8000) |
| Isolated Postgres/Chroma/Backend/Frontend | Pass (ports 15432 / 18001 / 18000 / 15173) |
| Empty DB → Alembic `001`–`008` | Pass |
| Failure-category seed (12 approved) | Pass |
| Register/login + project/incident/upload | Pass |
| Sample AWS AccessDenied analysis (`rules_only`) | Pass — **completed** after seed |
| Classification observed before seed | `aws_permission_failure` (persist failed until seed) |
| Image deps (`openai`, ST) via Dockerfile | Pass (no manual pip) |

## Live stack (non-destructive) confirmation

| Check | Result |
|-------|--------|
| Postgres / Chroma / Backend / Frontend | Healthy |
| Runtime volume backup | `backups/phase4_20260729T121836Z/` (gitignored) |

## Residual limitations

- Frontend still Vite-dev; backend still `--reload`.
- Isolated Chroma starts empty until product/research corpora are ingested.
- Bootstrap emails must use a non-reserved domain (e.g. `@example.com`), not `@*.local`.
