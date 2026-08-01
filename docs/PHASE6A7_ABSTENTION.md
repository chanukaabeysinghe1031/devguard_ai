# Phase 6A.7 — Abstention

Abstention is **intentional safe behavior**, not an error.

When blocking conditions fire, the system returns `INSUFFICIENT_EVIDENCE`, `CONFLICTED`, or `UNKNOWN` and does **not** propose a specific applied fix.

## Reason codes

- `OPEN_SET_UNKNOWN`
- `EVIDENCE_INSUFFICIENT`
- `VERIFIER_UNAVAILABLE`
- `VERIFIER_FAILED`
- `HYPOTHESES_TIED`
- `HIGH_CONTRADICTION`
- `GRAPH_INCOMPLETE`
- `ARTIFACTS_MISSING`
- `NO_SAFE_REMEDIATION`
- `HIGH_RISK_REMEDIATION`
- `CLASSIFIER_DISAGREEMENT`
- `INTERNAL_FAILURE`

## Blocking examples

- Open-set UNKNOWN → `UNKNOWN`
- Tied top hypotheses → `CONFLICTED`
- Required verifier FAIL → abstain / insufficient
- Critical-risk remediation → abstain
- Confidence below `MIN_FINAL_DIAGNOSIS_SCORE` → abstain

Version: `abstention_engine_v1`
