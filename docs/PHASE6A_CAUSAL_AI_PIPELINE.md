# Phase 6A — Causal AI Pipeline (overview)

Phase 6A extends the existing analysis spine with artifact acquisition, deep parsers, temporal localisation, and an evidence graph — **without** replacing Modules 6–9 diagnosis.

## Subphases

| Phase | Status | Deliverable |
|-------|--------|-------------|
| 6A.0 | Done | Architecture audit |
| 6A.1 | Done | Artifact bundle + parsers + GitHub acquisition |
| 6A.2 | Done | Temporal localisation + evidence graph + consistency |
| 6A.3 | Done | Hierarchical classification + open-set + disagreement |
| 6A.4+ | Not started | Hypotheses, ranking, verifiers, abstention, Causal UI |

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
  O --> D[Diagnosis + RAG + recommendations]
  H -.-> D
```

6A.2–6A.3 stages soft-fail. Hierarchical classification **extends** frozen categories and does **not** generate causal hypotheses.

## Important

- Temporal / graph relationships support later causal reasoning.
- Heuristic precedence is **not** confirmed causality.
- Missing artifacts → partial graph, never fabricated evidence.
- Open-set may return UNKNOWN; disagreement is an uncertainty signal only.
