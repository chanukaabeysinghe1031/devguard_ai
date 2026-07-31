# Phase 6A.5 Part 1B — Retrieval Orchestrator

**Status:** Delivered  
**Pipeline version:** `hypothesis_directed_v1`  
**Plan version:** `retrieval_plan_v1`

## Purpose

`HypothesisDirectedRetrievalOrchestrator` runs **independent retrieval sessions** after Phase 6A.4. It plans queries, invokes adapters, deduplicates items, and optionally persists results. It does **not** rank hypotheses or prove support/contradiction.

## Insertion point

```text
AnalysisExecutionService.execute
  → AnalysisOrchestrator (Modules 6–9)
  → _maybe_persist_artifact_bundle / 6A.2
  → _maybe_run_phase6a3
  → _maybe_run_phase6a4
  → _maybe_run_phase6a5_hypothesis_retrieval   # soft-fail; flag OFF = no-op
  → _persist_results
```

## Flag-off fallback

```mermaid
flowchart LR
  Flag{HYPOTHESIS_DIRECTED_RAG_ENABLED?}
  Flag -->|false| Dis[Run status DISABLED]
  Dis --> Skip[No DB writes / no adapter calls]
  Skip --> Base[Modules 6-9 diagnosis unchanged]
  Flag -->|true| Orch[Per-hypothesis sessions]
```

## Plan construction

```mermaid
flowchart TB
  Ctx[HypothesisRetrievalContext] --> PB[HypothesisRetrievalPlanBuilder]
  PB --> Q1[CAUSAL_CLAIM]
  PB --> Q2[ERROR_SIGNATURE]
  PB --> Q3[FAILURE_CATEGORY]
  PB --> Q4[RESOURCE / ACTION when present]
  PB --> Q5[HISTORICAL when enabled]
  Q1 --> F[Reject empty / oversized / secret-like]
  Q2 --> F
  Q3 --> F
  Q4 --> F
  Q5 --> F
  F --> D[Dedupe normalized queries]
  D --> B[Bound max_queries]
  B --> Plan[HypothesisRetrievalPlan]
```

## Adapter architecture around HybridRetrievalPipeline

```mermaid
flowchart TB
  Orch[HypothesisDirectedRetrievalOrchestrator] --> Art[ArtifactEvidenceRetrievalAdapter]
  Orch --> Graph[GraphEvidenceRetrievalAdapter]
  Orch --> Temp[TemporalEvidenceRetrievalAdapter]
  Orch --> Hyb[HybridPipelineHypothesisAdapter]
  Hyb --> Pipe[HybridRetrievalPipeline Module 9]
  Pipe --> Static[Static / lexical / vector]
  Pipe --> Hist[Historical org-scoped]
  Art --> Items[HypothesisRetrievedItem list]
  Graph --> Items
  Temp --> Items
  Hyb --> Items
  Items --> Dedup[Session dedupe]
  Dedup --> Sess[HypothesisRetrievalSession]
```

Unavailable adapters return explicit `SOURCE_UNAVAILABLE` — never simulated success. Hybrid adapter with `pipeline=None` is unavailable.

## Session failure isolation

```mermaid
flowchart TB
  Run[Retrieval run] --> A[Session A COMPLETE]
  Run --> B[Session B FAILED]
  Run --> C[Session C COMPLETE]
  B -.->|does not cancel| A
  B -.->|does not cancel| C
  Run --> Partial[Run status PARTIAL]
  Partial --> Diag[Modules 6-9 output intact]
```

- One failed session → continue others; persist partial package when persistence enabled.  
- Empty evidence → `NO_EVIDENCE` / insufficiency — **not** falsification.  
- Soft-fail at the execution-service hook — never block baseline diagnosis.

## Eligibility (summary)

| Eligible | Excluded |
|----------|----------|
| `READY_FOR_RANKING` | `CONTRADICTED`, `INVALID`, `DUPLICATE`, `REJECTED`, `FAILED`, `DISABLED` |
| Critic `ACCEPT_*` | Critic `CONTRADICTED` / `REJECT` |
| `INCOMPLETE` **with** `missing_evidence` | `INCOMPLETE` without missing evidence |

## Non-claims

- Part 1B = infrastructure, **not** causal ranking (`CAUSAL_RANKING_ENABLED` unused).  
- `SUPPORT_CANDIDATE` ≠ proven support; `CONTRADICTION_CANDIDATE` ≠ proven contradiction.  
- Retrieval failure does **not** disprove a hypothesis.  
- Evidence remains hypothesis-scoped after dedupe.
