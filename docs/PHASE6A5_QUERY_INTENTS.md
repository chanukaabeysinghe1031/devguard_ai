# Phase 6A.5 — Query Intents

Version: `hypothesis_query_intents_v1`

```mermaid
flowchart LR
  Claim[Causal claim] --> G[HypothesisQueryIntentGenerator]
  Missing[Missing evidence] --> G
  Expected[Expected / falsifying] --> G
  Graph[Graph seeds] --> G
  G --> I[QueryIntentType list]
```

Intent types include confirm claim, contradiction candidate, missing evidence, artifact relationship, historical analogue, official constraint, policy behavior, configuration requirement, prior-success difference, exact signature, resource/permission relationship, and novel signature.
