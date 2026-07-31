# Phase 6A.5 — Source Routing

Version: `hypothesis_source_router_v1`

```mermaid
flowchart TD
  Cat[Category / claim / intent] --> R[HypothesisRetrievalSourceRouter]
  R --> Sel[selected / required / optional / unavailable]
```

Examples: IAM → ARTIFACT+GRAPH+STATIC/DOCS; Terraform → ARTIFACT+GRAPH+TEMPORAL; dependency → ARTIFACT+TEMPORAL+STATIC; unknown → lexical/vector + artifact.
