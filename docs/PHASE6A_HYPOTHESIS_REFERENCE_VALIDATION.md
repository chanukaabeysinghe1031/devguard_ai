# Phase 6A — Hypothesis Reference Validation

`HypothesisReferenceValidator` rejects:

- unknown frozen category codes
- fabricated graph node/edge IDs (unless matching temporal primary event)
- fabricated evidence/artifact IDs
- secret-looking claim content
- downstream-symptom root nodes when a stronger temporal primary exists

Invalid candidates are not persisted as valid hypotheses.

`HypothesisCausalPathValidator` returns VALID / VALID_WITH_WARNINGS / PARTIAL / INVALID / NOT_APPLICABLE.
