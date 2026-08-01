# Phase 6A.7 — Final Confidence

Heuristic, configuration-weighted confidence decomposition.

**Not** a calibrated probability unless calibration experiments exist.

## Components (positive)

hypothesis ranking · evidence sufficiency · support · temporal · graph · classifier agreement · verifier support · constraint compliance · top-hypothesis margin

## Components (negative)

contradiction penalty · open-set penalty · missing-artifact penalty · remediation risk penalty · tie penalty

## Bands

`HIGH` · `MEDIUM` · `LOW` · `INSUFFICIENT`

Component breakdown is persisted under `confidence_breakdown` / `component_scores` in the final diagnosis JSONB payload.

Version: `final_confidence_v1`
