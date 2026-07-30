# Phase 5A — Docker Smoke Report

**Date:** 2026-07-30  
**Command:** `docker compose config && docker compose build && docker compose up -d`  
**Volumes:** live volumes **not** deleted (`down -v` not used)

## Compose status (post-rebuild)

| Service | Status |
|---------|--------|
| `devguard_backend` | healthy |
| `devguard_postgres` | healthy |
| `devguard_chroma` | healthy |
| `devguard_frontend` | up (HTTP 200) |

## Checks

| Check | Result |
|-------|--------|
| `GET /api/v1/health` | healthy |
| `GET /api/v1/health/ready` | ready / database connected |
| Frontend `http://localhost:5173/` | 200 |
| Register → login → create project | Pass |
| Restart backend+frontend | Pass |
| Project still readable after restart | Pass (`persist Smoke Proj`) |

## Notes

- Local `docker-compose.yml` bind-mounts `./frontend` and runs **Vite dev** (`npm run dev`) for MSc iteration. Image build succeeds; production static nginx packaging remains a deployment concern (AWS step), not a volume-destructive change here.
- Backend runs uvicorn without interactive `--reload` requirement for container health; confirm compose command matches deployment profile before AWS.

## Verdict

**Docker rebuild + runtime smoke + persistence after restart: PASS**
