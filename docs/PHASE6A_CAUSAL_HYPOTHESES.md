# Phase 6A — Competing Causal Hypotheses

**Phase:** 6A.4  
**Status:** Implemented (flags default OFF)

## Purpose

Generate **multiple competing** causal hypotheses for a suitable incident.

This phase produces **candidates only**. It does **not** verify, rank finally, remediate, or execute verifiers.

```mermaid
flowchart TB
  C[Hierarchical classification 6A.3] --> X[Hypothesis context]
  T[Temporal 6A.2] --> X
  G[Evidence graph 6A.2] --> X
  X --> R[Rule templates]
  X --> L[Optional LLM structured]
  R --> V[Reference + path validation]
  L --> V
  V --> D[Deduplicate]
  D --> K[Critic]
  K --> P[generation_prior_score]
  P --> S[Persist separately]
```

When flags are OFF:

```mermaid
flowchart LR
  Diag[Modules 6-9 diagnosis] --> Out[Existing predictions/recs]
  Diag -.-> Skip[Hypothesis stage skipped]
```

## Feature flags

| Flag | Default |
|------|---------|
| `CAUSAL_HYPOTHESIS_GENERATION_ENABLED` | false |
| `RULE_HYPOTHESIS_GENERATION_ENABLED` | false |
| `LLM_HYPOTHESIS_GENERATION_ENABLED` | false |
| `HYPOTHESIS_CRITIC_ENABLED` | false |

## Explicit non-claims

- Hypotheses are competing explanations, not verified root causes.
- `generation_prior_score` is **not** final causal ranking.
- Supporting evidence does not alone prove causality.
- No `VERIFIED` status in this phase.
