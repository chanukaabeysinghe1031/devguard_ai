# DevGuard AI — Phase 4 Full-System Audit

**Date:** 2026-07-29  
**Scope:** Backend, frontend, API, AI, Docker, env, docs, tests  
**Policy:** No deletions without confirmed safety. Findings classified below.

---

## Summary

| Class | Count (approx) |
|-------|----------------|
| Keep intentionally | Majority of scaffolds, dual Module 7/9 paths, schema-ahead tables |
| Defer with reason | Frontend tests, OpenAI circuit unit tests expansion, prod Docker image |
| Manual review | Env default skew RAG/LLM, Compose embedding default |
| Remove now | None confirmed safe for unconditional deletion |

---

## Findings

| ID | Finding | File(s) | Evidence | Risk | Decision | Action taken | Remaining |
|----|---------|---------|----------|------|----------|--------------|-----------|
| A1 | ~54 `/api/v1` endpoints across 9 routers | `api/v1/*` | Router inventory | Low | Keep | Documented in API report | — |
| A2 | Schema-only tables (notifications, audit_logs, feedback, evaluations, incident_reports, project_integrations) | ORM models | No API writers | Med | Keep / Defer | Documented as schema-ahead | Product modules later |
| A3 | SQLAlchemy repository layer unused by services | `infrastructure/repositories` | Services use session directly | Med | Keep | Documented scaffold | Optional DI later |
| A4 | `execution_router.py` re-export shim | `ai/orchestration/execution_router.py` | Unused import path | Low | Keep | Compat shim retained | Optional cleanup |
| A5 | Object storage stub raises NotImplemented | `object_storage.py` | S3/minio factory paths | Med | Keep | Explicit stub | Do not enable in prod |
| A6 | Dual query/rerank (baseline + hybrid) | `rag/query_builder.py`, `hybrid_*` | Both used | Low | Keep | Module 7 vs 9 | — |
| A7 | `keyword_only` accepted but aliased to hybrid path | config + hybrid pipeline | No specialised path | Med | Manual review | Documented | Implement or drop from API |
| A8 | `legacy_remediation_steps` deprecated | `recommendation.py` | Fallback in artifacts | Med | Keep | Intentional until data migrate | Future drop |
| A9 | No critical TODO/FIXME in app code | grep | Docs only | Low | Keep | — | — |
| A10 | `.env.example` enables RAG/LLM; Settings defaults false | `config.py`, `.env.example` | Default skew | High | Manual review | Documented in config audit; startup validation added for production | Split profiles later |
| A11 | Missing from `.env.example`: `API_V1_PREFIX`, `SERVICE_NAME`, `LOG_FORMAT` | config vs example | Present in Settings | Low | Defer | Added to `.env.example` in Phase 4B | — |
| A12 | Frontend is 2-page diagnosis shell | `frontend/src` | No full product UI | Low | Keep | Gated by approval | — |
| A13 | Frontend Dockerfile uses Vite dev server | `frontend/Dockerfile` | `npm run dev` | High for prod | Defer | Documented residual risk | Prod nginx image later |
| A14 | Backend Dockerfile uses `--reload` | `backend/Dockerfile` | Dev CMD | High for prod | Defer | Documented | Prod CMD without reload |
| A15 | Backend/frontend lack Compose healthchecks | `docker-compose.yml` | Only postgres/chroma | Med | Keep + improve | Healthchecks added in Phase 4B | — |
| A16 | Hardcoded demo credentials in DiagnosisPage defaults | `DiagnosisPage.tsx` | Default email/password | Med | Keep for local demo | Documented residual | Clear for shared deploys |
| A17 | No frontend automated tests | `frontend/` | Zero test files | Med | Defer | Documented | Optional later |
| A18 | `ci_runner_failure` seeded category | `seed.py` | Taxonomy extended | Low | Keep | Intentional Phase 3 fix | — |
| A19 | Federated secondary collection optional | `retriever.py`, config | Empty default | Low | Keep | Measured in retrieval comparison | Default choice documented |
| A20 | Failure-state detection in hybrid classifier | `hybrid_classifier.py` | Success demotion | Low | Keep | Phase 4 implemented | — |

---

## Orphan / unused classification notes

- **Not deleted:** repository interfaces, schema-ahead tables, object storage stub, execution_router shim — all intentional architecture scaffolds.
- **Not deleted:** dual baseline/hybrid retrieval — required by Module 7/9 contracts.
- **Deferred:** frontend production image, full product screens (hard approval gates).

---

## Environment variable audit (summary)

See `docs/CONFIGURATION_AUDIT.md` for the full matrix. Critical skew: safe code defaults vs demo `.env.example` for RAG/LLM/OpenAI.

---

## Test inventory

18 backend `test_*.py` modules (~176 tests) plus Phase 4B E2E regression package. Frontend: no unit tests (build verified).
