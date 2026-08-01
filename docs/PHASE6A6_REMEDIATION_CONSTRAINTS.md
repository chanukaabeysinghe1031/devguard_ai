# Phase 6A.6 — Remediation Constraints

Deterministic constraint extraction (`remediation_constraints_v1` / `constraint_extractor_v1`).

## Orchestration

```mermaid
flowchart TB
  CTX[Context + current state] --> O[Constraint orchestrator]
  O --> W[Workflow]
  O --> T[Terraform]
  O --> I[AWS/IAM]
  O --> S[Security]
  O --> R[Repo / operational]
  O --> D[Conflict detector]
  D --> SET[Constraint set]
```

## Properties

- Blocking vs informational severities
- Machine-readable rules (no LLM resolution of conflicts)
- Completeness may be `INSUFFICIENT` when sources missing
- Constraint completeness ≠ evidence sufficiency

Specialist docs: workflow, Terraform, AWS/IAM, security.
