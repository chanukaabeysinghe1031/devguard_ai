# Phase 4 — Production Hardening (Index)

**Module context:** closes production-hardening after Modules 1–9 / Phase 3 diagnosis.  
**Date:** 2026-07-29

This index links every Phase 4 / 4B deliverable. It does **not** by itself assert completion; see the final status section.

## Reports

| Deliverable | Document / path |
|-------------|-----------------|
| Full-system audit | [PHASE4_FULL_SYSTEM_AUDIT.md](./PHASE4_FULL_SYSTEM_AUDIT.md) |
| Earlier hardening notes | [PHASE4_AUDIT_REPORT.md](./PHASE4_AUDIT_REPORT.md) |
| API validation | [API_VALIDATION_REPORT.md](./API_VALIDATION_REPORT.md) |
| OpenAPI export | [openapi.json](./openapi.json) |
| Security matrix | [SECURITY_VERIFICATION_MATRIX.md](./SECURITY_VERIFICATION_MATRIX.md) |
| E2E regression (34 scenarios) | [E2E_REGRESSION_REPORT.md](./E2E_REGRESSION_REPORT.md) |
| Performance (p50/p95) | [PERFORMANCE_REPORT_PHASE4_FINAL.md](./PERFORMANCE_REPORT_PHASE4_FINAL.md) |
| Earlier performance draft | [PERFORMANCE_REPORT_PHASE4.md](./PERFORMANCE_REPORT_PHASE4.md) |
| Retrieval architecture comparison | [`datasets/benchmark/results/retrieval_architecture_comparison/`](../datasets/benchmark/results/retrieval_architecture_comparison/) |
| Configuration audit | [CONFIGURATION_AUDIT.md](./CONFIGURATION_AUDIT.md) |
| Clean-start verification | [CLEAN_START_VERIFICATION.md](./CLEAN_START_VERIFICATION.md) |
| Machine-readable perf/E2E | [`reports/performance/phase4/`](../reports/performance/phase4/) |

## Code / tests

| Area | Path |
|------|------|
| E2E scenarios | `backend/tests/e2e_regression/` |
| Security matrix tests | `backend/tests/e2e_regression/test_security_matrix.py` |
| OpenAI circuit tests | `backend/tests/test_openai_reliability.py` |
| Runner scripts | `scripts/testing/run_*.py` |
| OpenAPI export CLI | `backend/app/cli/phase4_export_openapi.py` |

## Default retrieval decision

Measured on gold labels (130 queries):

- **Single (research primary):** nDCG@5 **0.7096**, Precision@1 **0.7462**, p95 latency **53.6 ms**
- **Federated (research + product):** nDCG@5 **0.6729**, Precision@1 **0.7000**, p95 latency **31.4 ms**

**Default:** primary collection only. Federated retrieval remains **optional** via `CHROMA_SECONDARY_COLLECTION_NAME` when operators accept gold-metric dilution for broader corpus coverage.

Details: `datasets/benchmark/results/retrieval_architecture_comparison/comparison.md`

## Reliability / fallback (summary)

| Failure mode | Behaviour | Coverage |
|--------------|-----------|----------|
| OpenAI timeout/rate/auth/5xx | retry/backoff then soft-fail to local | provider + tests |
| Circuit open | skip external calls until reset | `test_openai_reliability.py` |
| Secondary Chroma unavailable | primary-only merge path | retriever soft-fail |
| Embedding unavailable | no silent hash fallback for ST | factory/health |
| Postgres temporary failure | readiness/analysis failure paths | health ready |
| Duplicate analysis submit | frontend guard + API conflict rules | UI + upload/analysis tests |

## Quality gates

| Gate | Command | Result |
|------|---------|--------|
| Ruff lint | `ruff check .` | Pass |
| Ruff format | `ruff format --check .` | Pass (211 files) |
| Mypy | `mypy app` | Pass (176 files) |
| Pytest | `pytest -q` | **245 passed**, 2 skipped, 2 deselected |
| Frontend lint | `npm run lint` (`tsc --noEmit`) | Pass |
| Frontend build | `npm run build` | Pass |
| Compose config | `docker compose config` | Pass |
| OpenAI package in image | `import openai` | Pass (2.50.0) |

### Skipped / deselected

| Item | Reason |
|------|--------|
| 2 deselected | `addopts = -m 'not embedding_integration'` — slow ST+Chroma integration tests excluded from default suite (still available with `-m embedding_integration`) |
| 2 skipped | `test_official_docs_corpus.py`, `test_retrieval_benchmark.py` skip at import when `scripts/dataset*` is not mounted into the backend container |

### Clean-start residual

Isolated clean-start was executed with `COMPOSE_PROJECT_NAME=devguard_phase4_clean` (separate ports/volumes). Live volumes were backed up under `backups/phase4_*` (gitignored) and left intact. See `CLEAN_START_VERIFICATION.md`.

## Final status gate

Phase 4 hardening commit/tag/push and isolated clean-start are complete. Use the completion phrase when the examiner checklist is fully satisfied.
