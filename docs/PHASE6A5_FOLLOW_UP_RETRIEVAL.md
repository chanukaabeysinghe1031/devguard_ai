# Phase 6A.5 — Follow-Up Retrieval

Version: `hypothesis_follow_up_v1`

```mermaid
flowchart TD
  Weak[Weak results] --> F[FollowUpPlanner]
  F -->|max 1 round| Q[New specs]
  Strong[Strong results] --> Skip[No follow-up]
```

Triggers: below min results/relevance, missing required sources, no exact ID match, missing expected observation, open-set unknown. Never removes org scope.
