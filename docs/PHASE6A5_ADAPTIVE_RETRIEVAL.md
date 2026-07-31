# Phase 6A.5 — Adaptive Hypothesis-Directed Retrieval

**Status:** Part 2 implemented  
**Migration:** none (016 not required)  
**Master flag:** `ADAPTIVE_HYPOTHESIS_RETRIEVAL_ENABLED` (default OFF)

When OFF, Part 1B path is unchanged. When ON:

```mermaid
flowchart TD
  A[Part 1B basic plan] --> B[Intent generation]
  B --> C[Adaptive planner]
  C --> D[Identifier extraction]
  D --> E[Source routing]
  E --> F[Execute adapters]
  F --> G{Validate?}
  G -->|flag ON| H[Validator]
  G -->|flag OFF| I[Features + relevance]
  H --> I
  I --> J{Follow-up weak?}
  J -->|yes once| F
  J -->|no| K[Persist metrics JSONB]
```

Pipeline version becomes `hypothesis_directed_v2`; plan version `retrieval_plan_v2`.

**Non-goals:** causal ranking, second RAG engine, migration 016.
