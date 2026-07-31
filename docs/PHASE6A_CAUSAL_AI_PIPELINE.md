# Phase 6A — Causal AI Pipeline (overview)

Phase 6A extends the existing analysis spine with artifact acquisition, deep parsers, temporal localisation, and an evidence graph — **without** replacing Modules 6–9 diagnosis.

## Subphases

| Phase | Status | Deliverable |
|-------|--------|-------------|
| 6A.0 | Done | Architecture audit |
| 6A.1 | Done | Artifact bundle + parsers + GitHub acquisition |
| 6A.2 | Done | Temporal localisation + evidence graph + consistency |
| 6A.3 | Done | Hierarchical classification + open-set + disagreement |
| 6A.4 | Done | Competing causal hypothesis generation (candidates only) |
| 6A.5 Part 1A | Done | Retrieval architecture audit |
| 6A.5 Part 1B | Done | Hypothesis-directed retrieval infrastructure (flags OFF; no ranking) |
| 6A.5 Part 2+ / 6A.6+ | Not started | Adaptive retrieval, causal ranking, remediations, verifiers, Causal UI |

## Pipeline (flags OFF = unchanged production path)

```mermaid
flowchart TB
  U[Upload / GitHub logs] --> M[Secret masking]
  M --> O[AnalysisOrchestrator Modules 6-9]
  M --> B[Artifact bundle 6A.1]
  B --> P[Deep parsers]
  P --> T[Temporal localisation 6A.2]
  T --> G[Evidence graph 6A.2]
  G --> C[Consistency 6A.2]
  O --> H[Hierarchical classification 6A.3]
  H --> Y[Causal hypotheses 6A.4]
  Y --> R5[Hypothesis-directed retrieval 6A.5 Part 1B]
  O --> D[Diagnosis + RAG + recommendations]
  Y -.-> D
  R5 -.-> D
```

6A.2–6A.5 Part 1B stages soft-fail. Hypotheses are **competing candidates**, not verified causes. Part 1B retrieval items are evidence **candidates** only (`SUPPORT_CANDIDATE` ≠ proven support).

## Important

- Temporal / graph relationships support later causal reasoning.
- Heuristic precedence is **not** confirmed causality.
- Missing artifacts → partial graph, never fabricated evidence.
- Open-set may return UNKNOWN; disagreement is an uncertainty signal only.
- Hypothesis `generation_prior_score` is not final ranking or verification.
- Phase 6A.5 Part 1B retrieval is hypothesis-scoped infrastructure; empty retrieval does not disprove a hypothesis.
- Phase 6A.5 Part 2 adds adaptive intents/routing/validation/relevance/follow-up behind OFF-by-default flags; `retrieval_relevance_score` is not causal support; no migration 016.
