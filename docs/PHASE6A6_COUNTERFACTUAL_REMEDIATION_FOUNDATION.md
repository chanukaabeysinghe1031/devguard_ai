# Phase 6A.6 Part 1 — Counterfactual Remediation Foundation

**Status:** Part 1 foundation complete; Part 2 generation available behind OFF flags  
**Not included:** Part 3 verifier execution, apply path, polished Causal UI

## Scientific position

Hypothesis-conditional **candidate** remediation plans under deterministic constraints — not “an LLM generates a fix,” and not a verified repair.

Every candidate is:
- conditional on one causal hypothesis;
- **not verified**;
- **not applied**;
- produced without external tools or production credentials.

## Pipeline insertion

```mermaid
flowchart LR
  R[6A.5 retrieval] --> E[6A.5 evidence assessment]
  E --> F[6A.6 foundation]
  F --> G[6A.6 Part 2 generation]
  G --> P[_persist_results]
  E -.-> D[Modules 6-9 diagnosis]
  F -.-> D
  G -.-> D
```

Soft-fail hooks: foundation then generation surface (generation runs inside foundation when flags ON)  
after `_maybe_run_phase6a5_evidence_assessment`, before `_persist_results`.

Part 2 persistence: migration `017_phase6a6_cf_generation` adds patch/risk/priority columns.  
See `docs/PHASE6A6_RULE_REMEDIATION_GENERATION.md` and related Part 2 docs.

## Flags (all OFF)

| Flag | Role |
|------|------|
| `COUNTERFACTUAL_REMEDIATION_ENABLED` | Master stage gate |
| `COUNTERFACTUAL_CONSTRAINT_EXTRACTION_ENABLED` | Extractors |
| `MINIMAL_CHANGE_PLANNING_ENABLED` | Planner skeletons |
| `COUNTERFACTUAL_TEMPLATE_REGISTRY_ENABLED` | Template resolve |
| `COUNTERFACTUAL_PERSISTENCE_ENABLED` | Migration 016/017 writes |
| `COUNTERFACTUAL_DEBUG_API_ENABLED` | Org-scoped GET APIs |
| `RULE_REMEDIATION_GENERATION_ENABLED` | Part 2 rule builders |
| `LLM_REMEDIATION_GENERATION_ENABLED` | Part 2 structured LLM |

Request options cannot force these ON when server flags are OFF.

## Flags-off fallback

```mermaid
flowchart TB
  A[Analysis run] --> B{counterfactual_remediation_enabled?}
  B -->|no| C[No-op / DISABLED]
  B -->|yes| D[Foundation service]
  D --> E[Options snapshot only]
  E --> F[Never overwrite diagnosis/recommendations]
```

## Persistence

Additive migration `016_phase6a6_cf_foundation`. Separate from product `recommendations` tables.

## Debug APIs (GET only)

Under `/analyses/{analysis_run_id}/counterfactual-remediation-*` with `require_org_reader` + `X-Organization-Id`. No apply endpoint.

## Related docs

- `PHASE6A6_COUNTERFACTUAL_CONTEXT.md`
- `PHASE6A6_CURRENT_AND_COUNTERFACTUAL_STATE.md`
- `PHASE6A6_REMEDIATION_CONSTRAINTS.md`
- `PHASE6A6_MINIMAL_CHANGE_PLANNING.md`
- `PHASE6A6_REMEDIATION_TEMPLATE_REGISTRY.md`
- `PHASE6A6_COUNTERFACTUAL_REMEDIATION_AUDIT.md`
