# Phase 6A.5 — Retrieval Validation

Version: `retrieval_result_validator_v1`

```mermaid
flowchart TD
  Item[Retrieved item] --> V[RetrievalResultValidator]
  V -->|ACCEPTED| Keep
  V -->|REJECTED_SCOPE/EMPTY/SECRET/...| Drop
```

Validates org scope, emptiness, secrets, provenance, archived/untrusted history. Does **not** decide support or contradiction.
