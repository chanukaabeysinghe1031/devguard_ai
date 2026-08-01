# Phase 6A.6 Part 1 — Counterfactual Remediation Architecture Audit

**Status:** Complete (Part 1 foundation audit only)  
**Baseline tag:** `v1.1.0-phase6a5-complete` (`482745e850e98b6e3b1a3d763f57be3c7613d373`)  
**Branch:** `feature/enterprise-incident-management-ui`  
**Alembic head at audit:** `015_phase6a5_hyp_retrieval`  
**Date:** 2026-08-01  

**Scientific position:** A counterfactual remediation framework that derives minimal, hypothesis-specific configuration changes under explicit workflow, infrastructure, security, and operational constraints — **not** “an LLM generates a fix.”

Part 1 stops at contracts, constraint extraction, current/counterfactual state, minimal-change planning skeletons, template registry, structural validation, and a feature-gated foundation stage. No verifier execution, no patch application, no GitHub writes, no Part 2 generation.

---

## 1. Test-count difference (not a regression)

### Reported totals

| Environment | Result | Notes |
|-------------|--------|-------|
| Host (Part 3 closeout) | **531 passed**, 2 deselected | Python 3.14 venv; repo root mounted; `scripts/dataset` present |
| Container (freeze `v1.1.0-phase6a5-complete`) | **516 passed**, **3 skipped**, 2 deselected | Backend image; Docker Compose |

### Collection (same revision)

| Environment | Collected | Deselected | Total items |
|-------------|-----------|------------|-------------|
| Host | **531 / 533** | 2 | 533 |
| Container | **517 / 519** | 2 | 519 |

**Host − container collected = 14.** Exact host-only nodes:

**`tests/test_official_docs_corpus.py` (10)** — collected on host only:

- `test_build_chunk_records_inherit_metadata`
- `test_chroma_metadata_contract`
- `test_chunking_reuses_shared_chunker_bounds`
- `test_corpus_version_constant`
- `test_downloader_rejects_unapproved_host`
- `test_duplicate_detection_skip_update_reject`
- `test_metadata_and_version_fields`
- `test_parser_extracts_aws_style_content_id`
- `test_parser_extracts_main_content_and_structure`
- `test_source_lists_are_official_hosts_only`

**`tests/test_retrieval_benchmark.py` (4)** — collected on host only:

- `test_benchmark_assets_exist_after_generation`
- `test_generate_queries_writes_expected_counts`
- `test_ir_metrics_basic`
- `test_propose_relevance_is_heuristic_only`

### Root cause (environmental)

Both modules use **module-level** `pytest.skip(..., allow_module_level=True)` when dataset/benchmark scripts are absent:

- `scripts/dataset` → official docs corpus helpers
- `scripts/dataset/benchmark` → retrieval benchmark helpers

On the **host**, those paths exist under the repo root → 14 tests collect and pass → **531**.  
In the **container**, those script trees are typically **not mounted** into the backend working directory → modules skip at import → **14 fewer collected tests** → **517**.

### Deselected (both environments)

`pyproject.toml` addopts: `-m 'not embedding_integration'`

| File | Deselected tests |
|------|------------------|
| `tests/test_embedding_integration.py` | Real sentence-transformer + Chroma integration (2 items) |

Optional marker; not a failure. Run explicitly with `-m embedding_integration` when Chroma + model cache are available.

### Skipped (container freeze: 3)

Consistent with:

1. Module-level skip of `test_official_docs_corpus.py` (scripts missing)
2. Module-level skip of `test_retrieval_benchmark.py` (scripts missing)
3. One additional runtime skip (commonly OpenAPI generation guard in Part 3, or DB/Chroma availability in optional paths)

No Phase 6A.5 tests were removed or renamed between the host Part 3 report and the freeze tag. Totals differ because of **host vs container mount / optional markers**, not because of a silent regression.

### Configuration differences

| Factor | Host | Container |
|--------|------|-----------|
| Python | 3.14 (local `.venv`) | 3.11 (image) |
| `scripts/dataset` | Present | Often absent → corpus/benchmark skip |
| Chroma | Optional / localhost | Compose service when up |
| Default pytest markers | Deselect `embedding_integration` | Same |
| DB hostname | Often `localhost` | `postgres` (Compose DNS) |

**Verdict:** Do not treat 516 vs 531 as a regression. Prefer Docker-first quality gates for Part 1 closure; document host totals separately when scripts are mounted.

---

## 2. Existing recommendation concepts (reuse vs separate)

### Reuse (patterns / infrastructure)

| Asset | Path | Reuse |
|-------|------|-------|
| Org-scoped debug API style | `analyses.py` + `phase6a5_service.py` | Same auth (`require_org_reader`), pagination clamp |
| Soft-fail stage hooks | `AnalysisExecutionService` | New `_maybe_run_phase6a6_*` |
| Feature flags / bounds | `config.py` + `.env.example` | Same OFF-default + validators |
| Secret masking | `domain/services/secret_masker.py` | Mandatory before context/fragments |
| Structured logging / cost options | Module 8 patterns | Observability only; Part 1 has no LLM |
| Parser outputs | `ai/artifacts/parsers/*` | Constraint + current-state inputs |
| Hypothesis / ranking domain | `domain/evidence_assessment/*`, `domain/hypotheses/*` | Eligibility + context inputs |
| Version constants pattern | `ai/evidence_assessment/versions.py` | Mirror for counterfactual versions |

### Must remain separate

| Baseline product | Phase 6A.6 counterfactual |
|------------------|---------------------------|
| `RecommendationGenerator` | Does **not** own remediation candidates |
| Tables `recommendations` / `recommendation_steps` | **Never** write counterfactual rows here |
| `context.recommendation` | Untouched when flags OFF/ON |
| Single primary prediction recommendation | Counterfactuals are per-hypothesis **candidates** |
| Labels implying “fix” / verified repair | Forbidden in Part 1 (`VERIFIED` / `FIXED` / `APPLIED` / `SUCCESSFUL` out of scope) |

Legacy recommendation APIs and persistence remain the product path. Counterfactual candidates are experimental research entities.

---

## 3. Single-answer assumptions still present

Baseline Modules 6–8 still assume one primary diagnosis path:

- Classifier → optional RAG → optional LLM root-cause → fused recommendation
- Schema bias toward a single `root_cause` with free-text alternatives
- Recommendations tied to the primary prediction

Phase 6A.4–6A.5 already introduced competing hypotheses and candidate ranking **without** claiming a proven root cause. Phase 6A.6 must continue that stance: every remediation candidate is **conditional on one hypothesis**, never a verified diagnosis.

---

## 4. Orchestrator insertion point (confirmed)

Phase 6A soft-fail stages live on **`AnalysisExecutionService`**, not inside `AnalysisOrchestrator.run`.

Current order (`analysis_execution_service.py`):

```
orchestrator.run(...)
→ _maybe_persist_artifact_bundle (+ nested 6A.2)
→ _maybe_run_phase6a3
→ _maybe_run_phase6a4
→ _maybe_run_phase6a5_hypothesis_retrieval
→ _maybe_run_phase6a5_evidence_assessment
→ _persist_results
```

**Approved Part 1 insertion:**

```
… → _maybe_run_phase6a5_evidence_assessment
  → _maybe_run_phase6a6_counterfactual_foundation   # NEW, feature-gated
  → _persist_results
```

Part 1 may run foundation only (eligibility, context, constraints, plan/template skeletons, optional candidate skeletons). It must **not** change existing recommendation generation.

---

## 5. Phase 6A.5 outputs required by 6A.6

| Input | Source | Required? |
|-------|--------|-----------|
| Causal hypotheses | `causal_hypotheses` / `context.options["causal_hypotheses"]` | Yes |
| Ranking + candidate selection | `context.options["hypothesis_evidence_assessment"]` + JSONB on retrieval run/session | Yes for eligibility |
| Support / contradiction / sufficiency | Same assessment payload | Yes |
| Hypothesis evidence links | `hypothesis_evidence_links` | Strongly preferred |
| Critic results | `hypothesis_critic_results` | Preferred |
| Evidence graph + consistency | 6A.2 tables / options | Preferred |
| Temporal localisation | 6A.2 | Preferred |
| Artifact bundle + parse results | 6A.1 | Required for concrete patches; missing → INCOMPLETE |
| Retrieved hypothesis items | 015 tables / options | Preferred for constraints from docs |
| Baseline recommendations | Product tables | Context only — **not authority** |

Without ranking/selection (flags OFF or empty), foundation should no-op or record `NO_ELIGIBLE_HYPOTHESES` without creating unsafe candidates.

---

## 6. Schema / persistence decision

### Existing JSONB that could hold experimental snapshots

- `hypothesis_retrieval_runs.configuration_snapshot`
- `hypothesis_retrieval_sessions.metrics` / snapshots
- `analysis_runs.output_summary`
- `causal_hypothesis_runs.context_snapshot`

### Decision for Part 1: **migration 016 is justified**

Counterfactual remediation is a long-lived, queryable research entity (runs, candidates, constraints, changes) with debug APIs and org-scoped listing. JSONB-only (as in 6A.5 Part 2/3 assessments) is insufficient for first-class candidates.

| Item | Value |
|------|-------|
| Head before Part 1 | `015_phase6a5_hyp_retrieval` (26 chars) |
| Proposed revision | `016_phase6a6_cf_foundation` (≤32 `version_num`) |
| Style | Additive only; no historical backfill |
| Isolation | `organization_id` / `project_id` / `incident_id` / `analysis_run_id` / `hypothesis_id` |
| Separation | No FKs into `recommendations`; optional FK to `causal_hypotheses` / analysis |

**Proposed tables (consolidated):**

1. `counterfactual_remediation_runs`
2. `counterfactual_remediation_candidates` (JSONB for current/counterfactual snapshots, effects, assumptions, rollback, risk summary)
3. `counterfactual_changes` (bounded change rows; fragments hashed/redacted)
4. `remediation_constraints`
5. `remediation_preconditions`
6. `remediation_verification_requirements`
7. Optional: `remediation_risk_signals` **or** JSONB on candidate — prefer typed table only if listing by risk type is needed in Part 1 APIs

When `COUNTERFACTUAL_PERSISTENCE_ENABLED=false`, no rows are written.

---

## 7. Safety boundaries (non-negotiable)

1. No automatic application (repo, IAM, Terraform apply, deploy, registry, prod restart).
2. No command execution in Part 1 (`terraform`, `actionlint`, `checkov`, `opa`, `docker`, `kubectl`, `aws`, package managers, arbitrary shell).
3. No unsafe generated commands from LLM/source text.
4. No broad permissions by default (`Action:"*"`, `Resource:"*"`, admin, disable scanners/TLS/encryption/tests/approvals).
5. All new flags default **OFF**; OFF ⇒ no diagnosis/recommendation change, no remediation rows, no extra LLM calls, no client-visible behavior change.
6. Organization isolation on every object.
7. Secrets masked; never embed secret **values** in patches — reference names only.
8. Artifacts and retrieved text are untrusted (prompt-injection defence even without LLM calls).
9. Candidate language only: never `VERIFIED` / `FIXED` / `APPLIED` / `DEPLOYED` / `SUCCESSFUL` in Part 1 statuses.
10. Source-code patches unsupported unless an exact causal config/source artifact exists; prefer INCOMPLETE over unsafe rewrite.

---

## 8. Gaps in artifact availability

| Gap | Impact |
|-----|--------|
| No workflow YAML in bundle | Workflow constraints/current-state incomplete |
| No Terraform / IAM policy artifact | IAM remediation skeletons incomplete or blocked |
| No plan JSON | Replacement-risk constraints weaker |
| No previous successful commit | “Restore last good” templates limited |
| Open-set unknown / missing graph path | Eligibility INELIGIBLE or INCOMPLETE |
| SCP / permissions boundary unknown | Record missing evidence; do not invent |

Fabricating current configuration fragments is forbidden.

---

## 9. Limits on source-code patch generation

Part 1:

- Prefer configuration / IaC / workflow / dependency / IAM artifacts.
- `SOURCE_CODE` artifact type exists in the taxonomy but concrete patch generation is out of scope unless a precise causal fragment is already parsed.
- Test failures must **never** produce delete/skip-test candidates.
- Max files/lines/chars enforced by settings bounds.

---

## 10. Legacy recommendation backward compatibility

- Keep `RecommendationGenerator` and `_persist_results` recommendation path unchanged.
- Do not alter recommendation API schemas for Part 1.
- Do not surface counterfactual candidates as “recommendations” in product APIs.
- Debug APIs under `/counterfactual-remediation-*` only; no “apply” endpoint.
- Prefer **no frontend** changes in Part 1.

---

## 11. Related systems inspected

| Area | Finding |
|------|---------|
| LLM / structured output | `reasoning_provider.py`, `output_validator.py`, prompt `v1` — unused by Part 1 generation |
| Cost/token tracking | Module 8 + hypothesis run fields — Part 1 records stage timing only |
| Uploaded-file security | Module 5 masking + type allowlists — reuse for fragment handling |
| GitHub workflow acquisition | Phase 5B — artifacts may arrive via upload or ingestion |
| Report / frontend contracts | Unchanged; Causal UI is 6A.9 |
| OpenAPI | 112 paths at 6A.5 Part 3 close; Part 1 adds debug GETs only |

---

## 12. Part 1 deliverable map (post-audit)

| Section | Deliverable |
|---------|-------------|
| Flags / bounds | All OFF + reserved generation flags |
| Domain contracts | Run, context, states, change, candidate, constraints, preconditions, failure condition, objective, plan, templates, verification (NOT_RUN/UNAVAILABLE/PENDING), rollback, risk signals |
| Extractors | Workflow, Terraform, AWS/IAM, security, repository/project, operational + orchestrator + conflict detector |
| Planner / templates | Contracts + skeleton registry (builders marked unimplemented) |
| Validator | Structural only — not independent verification |
| Foundation service | Flag-gated soft-fail stage |
| Persistence | Migration `016_phase6a6_cf_foundation` when implementing |
| APIs | Org-scoped debug GETs |
| Tests / docs | Scenarios 1–12 + quality gates |

**Out of Part 1:** rule/LLM patch generation, ranking, side-effect engine, verifier adapters, apply path, abstention, Causal UI.

---

## 13. Audit conclusion

Phase 6A.6 Part 1 should enter after Phase 6A.5 evidence assessment on `AnalysisExecutionService`, persist separately from product recommendations via additive migration **016**, keep all flags OFF by default, and treat every candidate as a conditional, unverified, hypothesis-linked minimal-change plan under deterministic constraints.

Implementation may proceed after this audit file lands.
