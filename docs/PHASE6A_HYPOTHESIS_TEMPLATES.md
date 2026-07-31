# Phase 6A — Hypothesis Templates

Deterministic templates live in `backend/app/domain/hypotheses/templates.py` (`TEMPLATES_V1`).

Families: IAM, Terraform, Workflow, Dependency, Container/Deployment.

Each template defines required/optional/contradicting signals, expected and falsifying observations, verification steps, category mapping, template ID/version, and diversity bucket.

Hypotheses are emitted **only** when minimum evidence tokens are present.
