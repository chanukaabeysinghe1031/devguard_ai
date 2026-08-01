# Phase 6A.6 Part 3 — Independent Verifier Engine

**Status:** Implemented (flags OFF by default)  
**Migration:** `018_phase6a6_verifiers`  
**Does not:** apply remediations, mutate the repository, call cloud APIs, or use LLMs as verifiers

## Purpose

Validate **temporary counterfactual states** produced by Phase 6A.6 Part 2 candidates using deterministic structural checks and optional external CLIs.

A PASS means the temporary workspace satisfied a verifier — **not** that the candidate is a proven root-cause fix or an applied repair.

## Feature flags (all default OFF)

| Flag | Role |
|------|------|
| `VERIFIER_ENGINE_ENABLED` | Master switch for the stage |
| `TERRAFORM_VERIFIER_ENABLED` | `terraform validate` / `plan` (never apply) |
| `ACTIONLINT_VERIFIER_ENABLED` | Workflow lint |
| `CHECKOV_VERIFIER_ENABLED` | IaC security scan |
| `OPA_VERIFIER_ENABLED` | Policy eval (needs bundle; else UNAVAILABLE) |
| `SECURITY_VERIFIER_ENABLED` | Built-in wildcard/secret static checks |
| `VERIFIER_PERSISTENCE_ENABLED` | Write runs/results tables |
| `VERIFIER_DEBUG_API_ENABLED` | Debug GET APIs (also accepted if counterfactual debug ON) |

Bounds: `MAX_CANDIDATES_FOR_VERIFICATION`, `MAX_VERIFIER_TIMEOUT_SECONDS`, `MAX_VERIFIER_STAGE_TIMEOUT_SECONDS`, `MAX_VERIFIER_STDOUT_CHARS`, `MAX_TEMP_WORKSPACE_FILES`, `MAX_TEMP_WORKSPACE_BYTES`.

Request options **cannot** force these flags ON.

## Pipeline insertion

```
foundation → generation → _maybe_run_phase6a6_verifier_engine → _persist_results
```

Soft-fail. Never overwrites `recommendations` / diagnosis.

## Temporary workspace

- `tempfile.TemporaryDirectory` under OS temp
- Candidate fragments / rendered patches written only there
- Path traversal rejected
- Always cleaned in `finally` / context manager
- Tools run with `cwd=temp_dir`, fixed argv, no `shell=True`

## Built-in adapters (always available)

- `json_schema`, `yaml_validator`, `hcl_fragment`, `iam_structural`, `dependency_manifest`, `security_static`

## Optional CLI adapters

Missing binaries → `UNAVAILABLE` (never fake PASS):

- `terraform_validate`, `terraform_plan` (`-refresh=false`, no apply)
- `actionlint`, `checkov`, `opa`

Docker installs these **best-effort**; image remains bootable without them. Healthcheck does not require tools.

## Persistence

Tables: `remediation_verification_runs`, `remediation_verification_results`  
Unique upsert key: `(organization_id, analysis_run_id, candidate_id)`

## Debug APIs (org-scoped GET only)

- `/analyses/{id}/counterfactual-verification-runs`
- `/analyses/{id}/counterfactual-verification-runs/{run_id}`
- `/analyses/{id}/counterfactual-verification-results`
- `/analyses/{id}/counterfactual-remediation-candidates/{candidate_id}/verification-consensus`
- `/analyses/{id}/counterfactual-remediation-candidates/{candidate_id}/verifier-logs`

No apply endpoints.

## Related docs

- `docs/PHASE6A6_CONSENSUS.md`
- `docs/PHASE6A6_COUNTERFACTUAL_VALIDATION.md`
- `docs/PHASE6A6_VERIFIER_ENGINE_AUDIT.md`
