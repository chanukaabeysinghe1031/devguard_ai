"""Phase 6A.2 audit notes — schema adjustments before implementation.

## Reuse without duplication

| 6A.1 asset | 6A.2 use |
|------------|----------|
| `GraphEntityPreview` | Source for `EvidenceGraphNode` via type/id mapping |
| `GraphRelationshipPreview` | Source for deterministic edges (`PARSER_DETERMINISTIC`) |
| `SourceLocation` | Copied onto temporal events and graph nodes |
| `StructuredParseResult` | Input to temporal normaliser + graph builder |
| `IncidentArtifactBundle` + ORM tables | Provenance / org scope; no schema change required |
| `EvidenceItem` (Module 6) | Left unchanged — diagnosis evidence remains separate |
| `IncidentEvent` timeline | Optional status events only; not the temporal model |

## Schema adjustments (additive)

1. **No changes to frozen parser preview dataclasses** — mapping layer normalises
   `RESOURCE`→`TERRAFORM_RESOURCE`, `USES`→`USES_ACTION`, etc.
2. **New domain packages** `domain/temporal` and `domain/evidence_graph` — do not
   overload `IncidentEvent` or `EvidenceItem`.
3. **Migration `012_phase6a2_temporal_graph`** — new tables only; no backfill.
4. **DerivationType / EdgeType / NodeType enums** live in evidence_graph domain;
   `LLM_INFERRED` reserved, unused in 6A.2.
5. **GraphRelationshipPreview.deterministic** drives derivation; heuristic temporal
   links use `TEMPORAL_HEURISTIC` and must never be labelled proven causality.

## Wiring

Temporal localisation and graph build run soft-fail after artifact-bundle
persistence in `AnalysisExecutionService` when flags are ON. Existing
orchestrator diagnosis path is unchanged; graph is not fed to LLM in 6A.2.
"""
