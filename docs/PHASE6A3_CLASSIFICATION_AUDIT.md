# Phase 6A.3 — Classification Audit

**Status:** Complete (implementation baseline)  
**Date:** 2026-07-31  
**Alembic head at audit:** `012_phase6a2_temporal_graph`  
**Next migration:** `013_phase6a3_hier_class`

---

## 1. Frozen category codes (do not rename)

Authoritative source: `backend/app/infrastructure/database/seed.py` → `APPROVED_FAILURE_CATEGORIES`.

| Code | Display name |
|------|----------------|
| `build_failure` | Build Failure |
| `test_failure` | Test Failure |
| `dependency_failure` | Dependency Failure |
| `configuration_failure` | Configuration Failure |
| `terraform_failure` | Terraform Failure |
| `docker_failure` | Docker Failure |
| `deployment_failure` | Deployment Failure |
| `aws_permission_failure` | AWS Permission Failure |
| `network_failure` | Network Failure |
| `security_misconfiguration` | Security Misconfiguration |
| `ci_runner_failure` | CI Runner Failure |
| `unknown_failure` | Unknown Failure |

There is **no** failure-category enum in `domain/enums.py`. Broader codes in dataset/docs are **not** seeded and must not replace these identifiers.

---

## 2. Existing aliases

- Repository lookup lowercases codes (`get_by_code`).
- No synonym table; classifier emits exact frozen codes only.
- Phase 6A.3 registry may resolve trivial aliases (e.g. whitespace / case) without inventing parallel codes.

---

## 3. Classifier outputs

| Field | Source |
|-------|--------|
| `category_code` | Frozen code string |
| `confidence` | float 0–1 (4 dp) |
| `rank` | 1..top_k |
| `matched_rules` | rule names, `keyword:*`, `policy:*`, `fallback:unknown` |
| `root_cause_summary` / `technical_explanation` / `impact_summary` | template text |
| Engine stamp | `rules-hybrid` / `1.0.0` |

**No separate trained ML classifier** is in production. Stage B reuses keyword / hybrid signals as the “learned/embedding” stage until a dedicated model is approved.

---

## 4. Confidence fields (Module 8)

- `ConfidenceAssessment`: raw/calibrated confidence, band, margin, reasons
- `UncertaintyAssessment`: score/level, ambiguity, conflicting categories
- `unknown_failure` applies calibrator/uncertainty penalties
- API thin classification blob: `{category, confidence, rank}` only

---

## 5. Fallback / unknown handling

| Condition | Behavior |
|-----------|----------|
| No rule/keyword hits | `unknown_failure` @ 0.35, `fallback:unknown` |
| Success markers, no failure | `unknown_failure` @ 0.90 |
| Top conf &lt; 0.40 | inject `unknown_failure` @ 0.40 |
| Persist missing code | FK falls back to `unknown_failure` |

---

## 6. Persistence today

- `predictions` rows with `predicted_label` = frozen code
- `reasoning_metadata.matched_rules`
- No hierarchy / open-set / disagreement columns
- Existing Phase 6A `map_failure_category()` exists but was **not** wired into classify/persist/API

---

## 7. Migration risks

| Risk | Mitigation |
|------|------------|
| Renaming frozen codes | Forbidden — hierarchy wraps codes |
| Historical relabel | Additive tables only; no backfill |
| Parallel category system | Single registry; L3 = frozen code |
| Alembic `version_num` length | Short revision id `013_phase6a3_hier_class` |

---

## 8. Exact reuse plan

1. Keep `HybridClassifier` as the sole production classifier for legacy output.
2. Extend `taxonomy_hierarchy` into `FailureTaxonomyRegistry` (L1 domains, L2 families, L3 = frozen code).
3. Add `HierarchicalClassificationOrchestrator` **after** existing classify + optional temporal/graph summaries.
4. Open-set, disagreement, and confidence breakdown are **additive** stages behind flags default OFF.
5. Persist enhanced results in new tables; leave `predictions` / UI category display unchanged when flags OFF.
6. LLM classification stage validates every code against the registry; reject invented labels.
7. Do **not** generate causal hypotheses, remediations, or verifiers in this phase.

---

## 9. Hierarchy mapping coverage (v1)

Every frozen code maps explicitly (100% coverage):

| Legacy code | Level 1 | Level 2 | Level 3 |
|-------------|---------|---------|---------|
| `build_failure` | APPLICATION | COMPILATION | `build_failure` |
| `test_failure` | TEST | UNIT_TEST | `test_failure` |
| `dependency_failure` | DEPENDENCY | PACKAGE_RESOLUTION | `dependency_failure` |
| `configuration_failure` | WORKFLOW | YAML_CONFIGURATION | `configuration_failure` |
| `terraform_failure` | INFRASTRUCTURE | TERRAFORM | `terraform_failure` |
| `docker_failure` | INFRASTRUCTURE | CONTAINER | `docker_failure` |
| `deployment_failure` | INFRASTRUCTURE | DEPLOYMENT | `deployment_failure` |
| `aws_permission_failure` | SECURITY | IAM_POLICY | `aws_permission_failure` |
| `security_misconfiguration` | SECURITY | SECURITY_POLICY | `security_misconfiguration` |
| `network_failure` | NETWORK | CONNECTION | `network_failure` |
| `ci_runner_failure` | RESOURCE | CI_RUNNER | `ci_runner_failure` |
| `unknown_failure` | UNKNOWN | UNKNOWN | `unknown_failure` |

Unmapped runtime codes → `UNKNOWN` / `LEGACY_UNMAPPED` with documentation (never silent drop).
