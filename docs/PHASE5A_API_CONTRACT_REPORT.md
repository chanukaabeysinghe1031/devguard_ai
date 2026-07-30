# Phase 5A — API Contract Report

**Date:** 2026-07-30  
**OpenAPI:** `docs/openapi.json` regenerated from FastAPI (`app.openapi()`), **58 paths**.

## New/confirmed Phase 5A paths

| Method | Path | Frontend client |
|--------|------|-----------------|
| GET | `/dashboard/summary` (+ trend, severity, categories, recent, active-analyses, activity) | `dashboardApi.ts` |
| GET/POST/DELETE | `/notifications*` | `notificationsApi.ts` |
| POST | `/incidents/{id}/reports` | `incidentsApi` / `reportsApi` |
| GET | `/reports`, `/reports/{id}`, download | `reportsApi.ts` |
| GET | `/history/incidents` | `historyApi.ts` |
| GET | `/evaluation/latest-metrics` | `evaluationApi.ts` |

## Validation

- Frontend uses `/api/v1` via `VITE_API_BASE_URL`
- Bearer + `X-Organization-Id` on org-scoped calls
- 401 → refresh then login redirect
- No stale calls to deleted diagnose-only helpers (`api/pipeline.ts`, `api/diagnosis.ts` removed)

## Gaps (documented, not contract bugs)

- Admin models / audit list endpoints absent → deferred UI
- PDF download not claimed

## Verdict

**Contracts aligned for implemented Phase 5A surfaces.**
