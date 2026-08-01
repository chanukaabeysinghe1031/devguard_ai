# Phase 6A.6 — Security Constraints

Extractor: `SecurityRemediationConstraintExtractor` (universal blocking rules).

## Always-on prohibitions (examples)

- Plaintext secrets / embedded credentials
- Wildcard admin permissions
- Public access by default
- Disabling encryption / TLS
- Removing scanners / policy gates
- Skipping or deleting tests as a “fix”
- Weakening approvals / branch protection

Injection text in logs/artifacts is sanitized and **does not** disable these constraints.
