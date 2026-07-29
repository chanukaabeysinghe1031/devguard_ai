# Phase 5 — Local Release Candidate Validation

**Date:** 2026-07-29  
**Branch:** `module-9-5-real-integration`  
**Prior tag:** `v0.9.0-phase4`

## 1. Fresh local startup

| Check | Result |
|-------|--------|
| Command | `docker compose down` then `docker compose up -d --build` |
| All healthy | Backend `/health` + `/health/ready`, Frontend `:5173`, Chroma heartbeat |
| Startup time | **356 s** wall clock including image rebuild; ~12 s from container start to all HTTP 200 |
| OpenAI package | Present (`openai 2.50.0`); API key configured in local `.env` (not committed) |
| Auth | Register/login verified in journey |
| Seed | Failure categories present (12 approved) |

## 2. User journey results

| Step | Result |
|------|--------|
| Register / login / logout / login again | Pass |
| Session `/auth/me` | Pass |
| Create / edit project | Pass |
| Archive / restore project (delete not hard-delete) | Pass |
| Create / edit incident | Pass |
| Upload + analyse + view diagnosis/evidence/sources/recommendations | Pass (AI section) |
| Analysis history after refresh/login | **Fixed** — now reloads from API (`listRecentAnalysisHistory`) |
| Project/incident hard delete in UI | N/A — diagnosis shell; API archive available |
| Persistence after backend restart | Pass (`PERSIST_MARKER_PHASE5` retained) |

Machine-readable: `reports/phase5/phase5_report.json`

## 3. AI validation (real fixtures)

| Scenario | Category | Status | Evidence | Sources | Recs |
|----------|----------|--------|----------|---------|------|
| AWS AccessDenied | `aws_permission_failure` | completed | 1 | 5 | 4 |
| Terraform undeclared | `terraform_failure` | completed | 1 | 5 | 4 |
| Docker COPY | `docker_failure` | completed | 1 | 5 | 3 |
| GHA runner offline | `ci_runner_failure` | completed | 1 | 5 | 5 |
| K8s ImagePullBackOff | `deployment_failure` | completed | 1 | 5 | 3 |
| Maven dependency | `build_failure` | completed | 1 | 5 | 3 |
| Gradle dependency | `build_failure` | completed | 1 | 5 | 3 |
| Python ModuleNotFound | `dependency_failure` | completed | 2 | 5 | 3 |
| npm ERESOLVE | `dependency_failure` | completed | 1 | 5 | 3 |
| Unknown vague log | `unknown_failure` | completed | 0* | 5 | 3 |
| Successful pipeline | `unknown_failure` (non-failure) | completed | 0 | 5 | 3 |

\* Zero log-evidence excerpts for vague unknown text is acceptable; category and grounded “insufficient signals” summary were correct.

End-to-end analysis latency (poll) typically **5–20 s**; first AWS run ~**63 s** (cold OpenAI/path warm-up).

## 4. Browser compatibility

| Browser | Method | Result |
|---------|--------|--------|
| Chromium (Chrome engine) | Playwright headless desktop + mobile | Pass — home + diagnose render; empty auth fields |
| Edge | Chromium-compatible UA + same SPA | Pass (HTTP 200) |
| Firefox | UA smoke + same SPA bundle | Pass (HTTP 200); full Gecko engine not installed in CI image |
| Responsive | `viewport` meta + Tailwind `sm:` / mobile Playwright | Pass |
| Dark theme | Product shell is dark-first (no light toggle) | Pass / known limitation |
| Broken UI | None observed in smoke | Pass |

Evidence: `reports/phase5/browser_smoke.json`

## 5. Error handling

| Case | Status | Notes |
|------|--------|-------|
| Empty file | 400 `EMPTY_FILE` | Pass |
| Whitespace-only | 400 `EMPTY_FILE` | Pass |
| Unsupported `.exe` | 415 | Pass |
| Oversized (>10MB) | 413 `FILE_TOO_LARGE` | Pass |
| Invalid JWT | 401 structured body, no stack | Pass |
| OpenAI / Chroma soft-fail | Covered by Phase 4 reliability tests + circuit breaker | Pass (prior) |

No secrets observed in error payloads.

## 6. Persistence

After `docker compose restart backend`, marker incident remained and was listable after re-login.

## 7. Performance observations

| Operation | Observation |
|-----------|-------------|
| Full rebuild startup | ~356 s (image build dominated) |
| Warm health | ~seconds |
| Register | ~1.2 s |
| Login | ~0.35 s |
| Upload | ~25–70 ms |
| Analysis completion | typically 5–20 s; cold ~60 s |
| Frontend build | <2 s |

Acceptable for local RC; first OpenAI-backed analysis is the slow path.

## 8–9. Bugs discovered / fixed

### BUG-P5-001 — Analysis history lost after refresh/logout

| Field | Detail |
|-------|--------|
| Description | Diagnosis history was React state only |
| Steps | Run analysis → refresh or logout/login → history empty |
| Expected | History reloadable from persisted analyses |
| Actual | Cleared |
| Root cause | No API hydration on session restore |
| Fix | `listRecentAnalysisHistory()` + clickable history reload |
| Files | `frontend/src/api/pipeline.ts`, `frontend/src/pages/DiagnosisPage.tsx` |
| Regression | `backend/tests/test_analysis_history_api.py` |

### BUG-P5-002 — Demo credentials pre-filled in auth form

| Field | Detail |
|-------|--------|
| Description | Default email/password encouraged unsafe shared demos |
| Fix | Cleared default email/password inputs |
| Files | `frontend/src/pages/DiagnosisPage.tsx` |

## 10. Remaining known issues

- Full multi-page product UI (projects/incidents CRUD screens) still gated — diagnosis shell only
- No light-mode toggle (dark-first shell)
- Firefox/Edge full engine automation not run (Chromium Playwright + UA smoke)
- `npm audit` reports transitive Vite/dev vulnerabilities — not introduced by Phase 5 feature work
- Rule confidence often reports `1.0` for strong rule hits (heuristic calibrator; not statistical probability)
- ZIP uploads still deferred (ADR-011)

## 11. UI polish

- Clickable recent analyses
- History loading indicator
- Removed hardcoded demo credentials
- Home/README status text updated for RC honesty

## 12. Regression tests

- `backend/tests/test_analysis_history_api.py` (pass)
- Existing e2e_regression suite still pass (74 tests in combined run with history test)

## 13. Documentation updates

- `README.md` status / Phase 5 pointer
- This report
- Harness: `scripts/testing/run_phase5_validation.py`

## 14. Release recommendation

**Recommend tag `v1.0.0-rc1`** for local release-candidate use.

Critical path (auth → upload → grounded diagnosis → persistence → error handling) validated. Remaining issues are non-critical / known gated scope.

## 15. Final status gate

Use `PHASE 5 COMPLETE — RELEASE CANDIDATE VALIDATED` only after commit + `v1.0.0-rc1` tag are published.
