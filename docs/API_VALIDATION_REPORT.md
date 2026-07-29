# API Validation Report — Phase 4B

**Date:** 2026-07-29  
**OpenAPI source:** generated from FastAPI (`docs/openapi.json`) — not a hand-maintained second specification.  
**Paths:** 41 path items / 53 HTTP operations under `/api/v1` plus `GET /`.

---

## Method

1. Exported live schema via `python -m app.cli.phase4_export_openapi`.
2. Cross-checked routers in `backend/app/api/v1/`.
3. Mapped automated coverage from `tests/test_auth.py`, `test_business_apis.py`, `test_uploads.py`, `test_analysis_artifacts_api.py`, `test_health.py`, `e2e_regression/`.

---

## Status-code conventions (verified)

| Code | Use | Evidence |
|------|-----|----------|
| 400 | Domain invalid requests where raised explicitly | Business/upload handlers |
| 401 | Missing/invalid/expired credentials | `test_auth.py` |
| 403 | Authenticated but unauthorised / wrong org | uploads + business APIs |
| 404 | Missing resource (same shape for other-org to avoid leakage where enforced) | health/business tests |
| 409 | Conflicts (duplicate file, membership, status) | uploads + auth register |
| 422 | Request schema validation (FastAPI) | Pydantic validation handler |
| 500 | Unhandled errors via `unhandled_exception_handler` (no stack in body) | `app/core/exceptions.py` |

---

## Endpoint groups

### Health
| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | `/api/v1/health` | none | Liveness |
| GET | `/api/v1/health/ready` | none | DB readiness |

### Authentication
| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | `/auth/register` | none | 201; 409 duplicate |
| POST | `/auth/login` | none | 200 tokens; 401 invalid |
| POST | `/auth/refresh` | refresh token | rotation; 401 reuse |
| POST | `/auth/logout` | refresh | revoke |
| GET | `/auth/me` | bearer | current user |
| POST | `/auth/change-password` | bearer | |

### Organizations / Projects / Pipeline runs / Incidents / Notes / Files / Analyses
All mutating and org-scoped reads require bearer auth + membership role checks. Ownership is enforced through organization membership and incident/project scoping (see business + upload tests for 403 cross-access).

Analysis artifacts:
- `GET /analyses/{id}` detail
- `GET .../status`, `/evidence`, `/sources`, `/recommendations`
- `POST .../cancel`
- Initiate/reanalyse return 202 when background mode is enabled

---

## Automated validation matrix

| Case | Covered | Primary tests |
|------|---------|---------------|
| Valid request | Yes | auth, business, uploads, analyses |
| Missing field | Yes | FastAPI 422 paths |
| Invalid field | Yes | status transitions, enums |
| Missing authentication | Yes | `test_auth.py` |
| Wrong user access | Yes | 403 upload/business |
| Missing resource | Yes | 404 paths |
| Conflict | Yes | 409 register/upload/membership |
| Unsupported file | Yes | `test_uploads.py`, security matrix |
| Oversized file | Yes | upload size validation tests |

---

## OpenAPI verification

- File: `docs/openapi.json`
- Generator: FastAPI `app.openapi()`
- Includes security schemes, request/response models from Pydantic schemas
- Examples: present where schemas define them; not every route has narrative examples (acceptable; schema is source of truth)

---

## Residual gaps

- Not every endpoint has a dedicated negative-path unit test (org member delete, some timeline edges).
- Frontend product screens remain out of scope; API surface exceeds the diagnosis shell UI.
- Production CORS/JWT enforcement depends on `ENVIRONMENT=production` startup validation.
