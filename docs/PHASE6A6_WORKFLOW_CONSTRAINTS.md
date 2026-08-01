# Phase 6A.6 — Workflow Constraints

Extractor: `WorkflowRemediationConstraintExtractor` for GitHub Actions / reusable workflows.

## Extracts

- Job existence and `needs` edges (acyclic)
- Permission least-privilege preservation
- Secret **references** only (`secrets.NAME`) — never literal values
- Environment / approval gate preservation

## Notes

Incomplete YAML → partial constraints + warnings. Prompt-injection comments cannot disable security rules.
