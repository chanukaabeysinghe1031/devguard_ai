# Phase 6A.1 — Artifact Bundle, Acquisition Extensions, and Deeper Parsers

**Status:** Implemented  
**Migration:** `011_phase6a_artifact_bundle` (after `010_phase5c_org_tenancy`)  
**Feature flags:** all **OFF** by default — existing analysis behaviour is unchanged until enabled.

This subphase does **not** build causal hypotheses, the final causal graph, verifier execution (6A.7), or the full Causal Analysis UI (6A.9).

---

## Goals delivered

1. Normalised `IncidentArtifactBundle` domain model with inventory, availability, acquisition errors, hashes, redaction status, and parser version metadata.
2. Organisation-scoped relational persistence (`analysis_artifact_bundles`, `analysis_artifacts`, `artifact_parse_results`) — **no backfill** of historical incidents.
3. Typed structured parser contracts + registry with deep parsers for:
   - GitHub Actions workflow YAML
   - CI / execution logs
   - Terraform HCL
   - Terraform plan JSON
   - AWS error / IAM policy JSON
   - Repository change metadata
4. GitHub acquisition extensions (read-only) for workflow YAML, run metadata, commit metadata, changed files, previous successful run metadata/logs — soft-fail per artifact.
5. Manual-upload artifact kind classification.
6. Wiring into the **existing** analysis spine behind flags (no parallel pipeline).
7. Minimal debug API: `GET /api/v1/analyses/{id}/artifact-bundle`.
8. Verifier probe stub that reports `DISABLED` / `UNAVAILABLE` — never fake PASS.

---

## Feature flags

| Flag | Default | Effect when ON |
|------|---------|----------------|
| `CAUSAL_ANALYSIS_ENABLED` | `false` | Master switch reserved for later causal stages (documented; not required for 6A.1 persistence). |
| `ARTIFACT_BUNDLE_ENABLED` | `false` | After analysis, build + persist artifact bundle from uploaded files. |
| `ARTIFACT_PARSING_ENABLED` | `false` | Run deep parsers when building a bundle. |
| `GITHUB_ARTIFACT_ACQUISITION_ENABLED` | `false` | During GitHub ingestion, collect extended artifacts and store as system uploads. |
| `ARTIFACT_MAX_CONTENT_CHARS` | `500000` | Truncation bound for acquired/parsed text. |

Clients **cannot** bypass these via request options. When flags are off, GitHub log ingestion, manual upload, RAG, recommendations, and incident pages behave as before.

---

## Migration 011

Additive tables only:

- `analysis_artifact_bundles` — org + incident scoped snapshot (available/missing/errors/quality/redaction + JSON bundle snapshot without raw content).
- `analysis_artifacts` — per-artifact inventory (kind, source, hash, acquisition/redaction status, optional `uploaded_file_id`).
- `artifact_parse_results` — structured parser output (entities, relationships, diagnostics, evidence candidates, warnings/errors, extraction quality).

Downgrade drops these three tables. No fabricated rows for historical analyses.

---

## Architecture (reuse spine)

```
Upload / GitHub logs ──► UploadService (mask secrets)
        │
        ▼
AnalysisExecutionService ──► AnalysisOrchestrator (Module 6–9)
        │
        └── (if ARTIFACT_BUNDLE_ENABLED) ArtifactBundleService
                 ├── classify uploads
                 ├── ParserRegistry (if ARTIFACT_PARSING_ENABLED)
                 └── persist org-scoped bundle

GitHubIngestionService ──► logs (always)
        └── (if GITHUB_ARTIFACT_ACQUISITION_ENABLED) GitHubArtifactAcquisition
                 └── soft-fail extra files via UploadService
```

---

## Parser contract

Every parser returns `StructuredParseResult`:

- `entities`, `relationships`, `diagnostics`, `evidence_candidates`
- `source` locations where applicable
- `parser_name` / `parser_version`
- `warnings`, `errors`, `extraction_quality`
- **No** causal hypotheses

Registry: `build_default_parser_registry()`.

Taxonomy: frozen category codes unchanged; `map_failure_category()` adds Level-1 hierarchical mapping around them.

---

## Acquisition coverage (GitHub)

| Artifact | Source | Soft-fail |
|----------|--------|-----------|
| Failed workflow logs | Existing download + extract | Yes (pre-existing) |
| Workflow YAML at failed commit | Contents API + workflow path | Yes |
| Workflow-run metadata | Webhook/API snapshot JSON | Yes |
| Triggering commit metadata | Commits API | Yes |
| Changed-file metadata | Compare API (parent…head) | Yes |
| Previous successful run metadata | List runs (conclusion=success) | Yes |
| Previous successful logs | Log download + extract (bounded) | Yes |

Missing/inaccessible artifacts are recorded explicitly (`missing_artifacts` / `collection_errors`). One failure does not abort analysis.

Permissions remain **read-only** (Actions + metadata + contents). No write scopes, no cloud account access, secrets masked before persist/LLM.

---

## Limitations (explicit)

- No causal graph / hypothesis generation (6A.2+).
- No verifier execution (6A.7); tools report UNAVAILABLE/DISABLED.
- No full Causal Analysis frontend (6A.9); only debug API for bundle status.
- Terraform/AWS acquisition from cloud accounts is **out of scope**; those kinds come from manual upload or future phases.
- Previous-success log collection stores a bounded first extracted file, not the full archive ZIP as a single blob.
- Contents API requires Contents read permission on the GitHub App installation; if denied, workflow YAML is marked missing.

---

## Key files

| Area | Path |
|------|------|
| Domain | `backend/app/domain/artifacts/` |
| Parsers | `backend/app/ai/artifacts/parsers/` |
| Bundle service | `backend/app/ai/artifacts/bundle_service.py` |
| Upload classifier | `backend/app/ai/artifacts/upload_classifier.py` |
| GitHub acquisition | `backend/app/ai/artifacts/github_acquisition.py` |
| Verifier stub | `backend/app/ai/artifacts/verifier_status.py` |
| Migration | `backend/alembic/versions/011_phase6a_artifact_bundle.py` |
| ORM | `backend/app/infrastructure/database/models/analysis_artifact_bundle.py` |
| Provider extensions | `backend/app/domain/interfaces/github_provider.py`, `github_app_provider.py`, `fake_github_provider.py` |
| Docs (this) | `docs/PHASE6A_ARTIFACT_BUNDLE_AND_PARSERS.md` |

---

## Tests

- `backend/tests/test_phase6a_parsers.py` — domain + deep parsers + fixtures
- `backend/tests/test_phase6a_artifact_bundle.py` — classifier, acquisition, flags-off, org isolation, verifier stub
- Existing GitHub ingestion / upload / secret-masking / migration suites remain the regression gates

---

## Next (requires separate approval)

**Phase 6A.2** — evidence graph construction from parse results (not started).
