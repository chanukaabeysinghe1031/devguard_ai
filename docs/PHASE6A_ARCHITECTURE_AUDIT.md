# Phase 6A — Architecture Audit and Research Implementation Plan

**Status:** Complete (Phase 6A.0 only — **no pipeline implementation in this document**)  
**Date:** 31 July 2026  
**Authority:** Subordinate to `docs/MASTER_ARCHITECTURE.md`, `docs/PROJECT_CONSTITUTION.md`, `docs/ARCHITECTURE_DECISION_LOG.md`  
**Scope gate:** Implement nothing until this audit is accepted and each subsequent subphase is explicitly approved.

---

## 1. Purpose and research framing

### 1.1 Research gap (product framing)

Existing CI/CD failure analysis typically treats logs, workflow definitions, IaC, and cloud evidence as separate inputs. Prediction models estimate failure likelihood; LLM/RAG systems often infer causes from logs alone without a verifiable causal mechanism across artifacts, and without independent verification of remediation.

### 1.2 Target scientific contribution (must implement toward)

> A neuro-symbolic, verifier-guided, cross-artifact causal reasoning pipeline that diagnoses CI/CD failures by constructing and testing causal hypotheses across workflow logs, GitHub Actions configuration, Terraform dependencies and cloud evidence before generating independently validated remediation recommendations.

### 1.3 What this is **not**

- Not “rules + ML + RAG + LLM” as the contribution claim.
- Not a parallel second AI product.
- Not Module 10 multi-agent productisation unless separately approved.
- Not automatic Terraform apply, Git commits, or production cloud mutation.

### 1.4 Naming note

Canonical roadmap **Phase 6 — AI Intelligence** (Modules 6–10) already delivered Modules 6–9. **Phase 6A** is a **research extension** of that spine (causal graph + verifiers + abstention). Do not confuse with API-spec “Phase 6 UX” or dataset-spec “Phase 6 evidence subsets.”

---

## 2. Current system snapshot (as-built)

| Area | State |
|------|--------|
| Modules 1–9 | Delivered (foundation → hybrid retrieval) |
| Phase 5A–5D | Incident UI, GitHub App, multi-tenant org, branding |
| Migrations | `001` … **`010_phase5c_org_tenancy`** → next is **`011_*`** |
| ADRs indexed | ADR-005, ADR-012, ADR-013 (next free research ADR suggested: **ADR-014** or dedicated **ADR-006** only if index is expanded carefully — prefer **ADR-014** to avoid colliding with historical gaps) |
| Causal / hypothesis / verifier code | **Absent** (zero product matches) |
| Trained ML classifier | **Deferred** (hybrid = rules + keyword boosts only) |

---

## 3. Reusable spine (reuse unchanged where possible)

### 3.1 Orchestration

| Asset | Path | Reuse |
|-------|------|--------|
| `AnalysisOrchestrator` | `backend/app/ai/orchestration/analysis_orchestrator.py` | Stage runner, soft-fail, progress callbacks |
| `AnalysisExecutionService` | `backend/app/application/services/analysis_execution_service.py` | Persist runs, clamp flags |
| `analysis_task` | `backend/app/application/services/analysis_task.py` | Sync / BackgroundTasks scheduling |
| `AdaptiveExecutionRouter` | `backend/app/ai/orchestration/adaptive_router.py` | Module 8 initial + post-retrieval routing |
| Module 8 models | `backend/app/ai/orchestration/models.py` | Confidence / uncertainty / retrieval quality / budget |
| Factory | `backend/app/ai/factory.py` | Provider wiring |

**Current stage order (simplified):** validate → mask → parse → preprocess → signals → classify → evidence → Module 8 calibrate → route → RAG (soft) → post-route → recommendations → reasoning (soft) → validate → fusion.

**6A implication:** insert causal stages **after evidence** (and optionally after RAG) as **soft-fail-capable** stages behind feature flags. Do not fork a second orchestrator.

### 3.2 Classification and taxonomy

| Asset | Notes |
|-------|--------|
| `HybridClassifier` + `rule_based_classifier.py` | Deterministic MVP classifier |
| Seeded `failure_categories` | 12 frozen codes including `terraform_failure`, `aws_permission_failure` |
| `predictions` table | Primary label + `reasoning_metadata` JSONB |

**Hard gate:** changing frozen taxonomy codes requires **explicit separate approval**. Hierarchical Level 1–3 must **map onto** existing codes, not silently replace them.

### 3.3 Evidence, recommendations, reasoning

| Asset | Reuse |
|-------|--------|
| `EvidenceExtractor` | Line windows / stack traces → `evidence_items` |
| `RecommendationGenerator` | Template remediations + optional LLM overlay |
| `RootCauseAnalyzer` + reasoning providers | Local grounded + OpenAI with circuit breaker |
| Guardrails / prompt / JSON parse | Keep for LLM hypothesis generation |

### 3.4 RAG (Module 9)

| Asset | Reuse |
|-------|--------|
| `HybridRetrievalPipeline` | Modes: embedding_only / hybrid_static / hybrid_with_history |
| Static + lexical + historical retrievers | Org-scoped history; history off by default |
| Chroma + ST / hash embeddings | Soft-fail; no silent ST→hash |
| `knowledge_base/*.md` | AWS IAM, Terraform, Docker, npm, CI runner |

**6A implication:** keep baseline retrieval; add **hypothesis-directed** query builder as an extension, not a replacement.

### 3.5 GitHub ingestion (Phase 5B)

| Collected today | Gap |
|-----------------|-----|
| Workflow run metadata | — |
| Failed job/step **logs** (ZIP → `.log`/`.txt`) | — |
| Auto incident + analysis | — |
| Connection filters / webhook durability | — |
| | Workflow YAML at failing commit |
| | Reusable workflows, action pins |
| | Previous successful run logs |
| | Terraform / plan / cloud artifacts from repo |

Provider is **observe-only** (ADR-005). Acquisition extensions must stay within GitHub App permissions (read contents where already granted; never invent write scopes).

### 3.6 Uploads and parsers (today = metadata only)

| Type | Parser | Depth |
|------|--------|-------|
| Logs | `LogMetadataExtractor` | Counts / error-keyword lines |
| Workflow YAML | `YamlMetadataExtractor` | Name + job keys |
| JSON | `JsonMetadataExtractor` | Root type |
| Terraform | `TerraformMetadataExtractor` | Regex resource/module names |

Interface: `ArtifactParser` in `domain/interfaces/parsers.py` — **extend**, do not duplicate.

Allowed upload types: `.log`, `.txt`, `.yaml`, `.yml`, `.tf`, `.tfvars`, `.json`. ZIP still **deferred** (ADR-011).

### 3.7 Persistence patterns

| Pattern | Use for 6A |
|---------|------------|
| `analysis_runs.output_summary` JSONB | Prototype causal payloads early |
| `predictions.reasoning_metadata` | Hypothesis summaries for FE |
| New tables (migration `011+`) | Queryable graph / hypotheses / verifiers |
| Org denormalization (010) | Every new high-volume table needs `organization_id` where listed |

Live analysis does **not** write the `evaluations` table (offline/MSc metrics). Per-run “evaluation_metadata” lives in `output_summary`.

### 3.8 Frontend (Phase 5A)

Incident detail tabs: Overview, Evidence, Sources, Recommendations, Timeline, Notes, Files, Resolution, Report + analysis progress page.

**Missing:** Causal Analysis tab, graph viz, hypothesis cards, verifier panels, confidence decomposition UI, abstention panel.

API client: `frontend/src/api/analysesApi.ts` — extend; do not create a parallel client stack.

### 3.9 Config / Docker / tests

- Flags pattern: `ENABLE_RAG` / `ENABLE_LLM` / hybrid knobs — **mirror** for causal (`CAUSAL_ANALYSIS_ENABLED`, etc.).
- Docker: postgres, chroma, backend, frontend only. **No** Terraform CLI, actionlint, Checkov, OPA in images today.
- Strong regression coverage: AI pipeline, hybrid retrieval, classifier, GitHub ingestion, uploads, Phase 5C tenancy.

---

## 4. What must be refactored

| Item | Why |
|------|-----|
| Generic RAG as sole retrieval story | Becomes **baseline** beside hypothesis-directed retrieval |
| Single `root_cause.summary` UX | Must support competing hypotheses + verification status |
| Analysis progress stage list (FE) | Must show new causal stages without breaking old runs |
| Metadata-only “parsers” | Must grow into entity/relationship extractors |
| Recommendation “verified by LLM tone” | Must map to VERIFIED / PARTIAL / NOT_VERIFIED / REJECTED / ABSTAIN |
| Confidence as one band | Must decompose into measurable components |

Refactor **in place** inside `AnalysisOrchestrator` / services — no parallel `CausalOrchestratorV2` product path.

---

## 5. What must be extended (new modules behind flags)

Ordered by Phase 6A subphases (implementation **after** audit approval):

| Subphase | Deliverable |
|----------|-------------|
| **6A.1** | `IncidentArtifactBundle` + acquisition gaps + deep parsers |
| **6A.2** | Temporal localiser + evidence graph (relational JSON, not Neo4j) |
| **6A.3** | Hierarchical taxonomy **mapping** + open-set detector |
| **6A.4** | Competing `CausalHypothesis` generation (templates + validated LLM JSON) |
| **6A.5** | Hypothesis-directed RAG + ranker + disagreement analyser |
| **6A.6** | Counterfactual remediation model + temp workspaces — **Part 1 foundation complete** (flags OFF; migration 016; no apply/verifiers) |
| **6A.7** | Verifier suite adapters (optional tools) |
| **6A.8** | Confidence decomposition + abstention engine |
| **6A.9** | Frontend Causal Analysis experience |
| **6A.10** | Dataset causal-chain schema + baselines harness |
| **6A.11** | Security, regression, docs, quality gates |

---

## 6. New domain entities (proposed)

Prefer additive migration **`011_phase6a_causal_core`** (name TBD) after approval.

| Entity | Purpose | Notes |
|--------|---------|--------|
| Artifact bundle snapshot | Availability / missing / quality | May start as JSON on `analysis_runs` |
| Graph nodes / edges | Cross-artifact causal graph | Deterministic vs inferred vs LLM-proposed flags |
| Causal hypotheses | Competing claims | Link evidence IDs only if they exist |
| Hypothesis–evidence links | Support / contradict / missing | |
| Remediation candidates | Hypothesis-tied patches | Isolated workspace only |
| Verifier runs / findings | Independent checks | Status includes UNAVAILABLE |
| Confidence components | Decomposed scores | Config-driven weights |
| Abstention decisions | Explicit insufficient evidence | |
| Incident outcomes | Human confirmation | Extends feedback; no auto-retrain |

**Reuse first:** `evidence_items`, `recommendations`, `predictions`, `uploaded_files`, `retrieved_documents`, `feedback`.

Do **not** fabricate graph data for pre-6A historical analyses.

---

## 7. Migration risks

| Risk | Mitigation |
|------|------------|
| Large JSON growth in `output_summary` | Cap sizes; move to tables once stable |
| Taxonomy hierarchy vs frozen codes | Mapping table; keep legacy `predicted_label` |
| GitHub Contents API rate limits | Soft-fail acquisition; record `artifact_collection_errors` |
| Optional verifiers missing in Docker | Status `UNAVAILABLE`; never fake PASS |
| Temp workspace disk / timeouts | Hard limits, cleanup, no production creds |
| Org isolation on new tables | `organization_id` + membership checks on every API |
| Breaking FE stage polling | Backward-compatible stage names + additive stages |
| Evaluation conflation | Keep retrieval benchmark separate from causal metrics |

Downgrade path: feature flags default **off**; legacy analyses unchanged.

---

## 8. Optional external tools (graceful degradation)

| Tool | Role | If missing |
|------|------|------------|
| `actionlint` | Workflow lint | `UNAVAILABLE` |
| Terraform CLI | fmt / validate / (isolated) plan | `UNAVAILABLE`; never apply |
| Checkov | Security scan of candidate files | `UNAVAILABLE` |
| OPA | Policy packs if present | Disabled by default |
| Sentence-Transformers / Chroma | Already optional via Module 9 | Unchanged |

All tools: allowlisted commands, timeouts, no `shell=True` with LLM text, no production credentials in verifier env.

---

## 9. Graceful degradation rules (non-negotiable)

1. Missing artifact → record in `missing_artifacts`; never invent content.
2. Soft-fail causal stages → retain classifier + template recommendations (today’s behaviour).
3. LLM hypothesis generation fails schema → reject response; fall back to deterministic templates.
4. Verifier unavailable → lower verification confidence; never label VERIFIED.
5. Graph path incomplete → abstain or PARTIALLY_VERIFIED at most.
6. Request options cannot bypass server `CAUSAL_*` / existing `ENABLE_*` flags.
7. Abstention is a first-class successful outcome, not an error.

---

## 10. Target logical pipeline (map to existing stages)

```text
Artifacts → secure acquisition → parse → temporal graph + dependency graph
  → causal evidence graph → hierarchical/open-set classify
  → competing hypotheses → support/contradict/missing
  → hypothesis-directed retrieval → rank → counterfactuals
  → independent verifiers → confidence + abstention
  → VERIFIED | PARTIALLY_VERIFIED | NOT_VERIFIED | REJECTED | INSUFFICIENT_EVIDENCE
  → human feedback / outcomes
```

Map onto `AnalysisOrchestrator` as additive stages, not a separate service mesh (no Kafka/Celery/Neo4j/K8s operators for MVP).

---

## 11. Frontend impact (6A.9 preview)

Add **Causal Analysis** experience (tab or nested route) with:

- Overview (status badge, leading hypothesis, missing evidence)
- Graph (with accessible table fallback)
- Hypotheses / Evidence / Counterfactual repairs / Verification / Confidence / Abstention

Never show a green “Verified” badge from LLM text alone.

Preserve all existing tabs and GitHub / upload / notification flows.

---

## 12. Dataset and evaluation impact (6A.10 preview)

Current benchmark (`datasets/benchmark/`) is **retrieval graded relevance**, not causal chains.

Need new (additive) case schema including `gold_causal_chain`, artifact fixtures, abstention labels, and baselines B1–B7 vs proposed pipeline — without breaking existing retrieval evaluation CLI.

---

## 13. Security constraints (carry into all subphases)

- Mask secrets before parse/LLM/verifier logs.
- No Terraform apply, no Git write, no IAM mutation.
- Temp workspaces only; path traversal / archive safety.
- Allowlisted verifier binaries only.
- Org-scoped APIs; viewers cannot trigger expensive verification unless existing RBAC allows writers.
- Audit verifier runs with correlation IDs.

---

## 14. Proposed configuration (document only — add in later subphase)

Illustrative names (to land in `.env.example` during 6A.1+):

```text
CAUSAL_ANALYSIS_ENABLED=false
EVIDENCE_GRAPH_ENABLED=false
HYPOTHESIS_GENERATION_ENABLED=false
COUNTERFACTUAL_VERIFICATION_ENABLED=false
ACTIONLINT_ENABLED=false
TERRAFORM_VERIFIER_ENABLED=false
CHECKOV_ENABLED=false
OPA_ENABLED=false
MAX_HYPOTHESES=5
```

Defaults **false** until quality gates pass.

---

## 15. Delivery discipline

1. **This audit (6A.0)** must be accepted before coding.
2. Commit **one subphase at a time** (6A.1 → 6A.11).
3. Do not start the next subphase if prior quality gates fail.
4. Do not implement Module 10 multi-agent product scope under 6A.
5. Do not change frozen org roles or taxonomy codes without separate approval.

---

## 16. Audit conclusions

| Question | Answer |
|----------|--------|
| Can we extend the existing pipeline? | **Yes** — orchestrator + Module 8/9 + GitHub + uploads are the correct spine. |
| Largest evidence gap? | Automatic cross-artifact acquisition (workflow YAML / IaC / cloud) + deep parsers. |
| Largest product gap? | Competing hypotheses, graph, independent verifiers, abstention, FE causal UX. |
| Immediate migration? | **Not in 6A.0.** First implementation migration expected as `011_*` in 6A.1/6A.2 after approval. |
| External graph DB? | **No** for MVP. |
| Automatic remediation? | **Forbidden.** |

### Explicit non-implementation statement

**Phase 6A.0 delivers this audit only.** No causal tables, parsers, verifiers, or UI changes are included with this document. Implementation requires separate approval to proceed to **Phase 6A.1**.

---

## 19. Phase 6A.1 implementation references (post-approval)

Phase 6A.1 is implemented. See `docs/PHASE6A_ARTIFACT_BUNDLE_AND_PARSERS.md`.

| Deliverable | Location |
|-------------|----------|
| Migration `011_phase6a_artifact_bundle` | `backend/alembic/versions/011_phase6a_artifact_bundle.py` |
| Domain bundle + taxonomy mapping | `backend/app/domain/artifacts/` |
| Parser registry + deep parsers | `backend/app/ai/artifacts/parsers/` |
| Bundle persist service | `backend/app/ai/artifacts/bundle_service.py` |
| Upload classifier | `backend/app/ai/artifacts/upload_classifier.py` |
| GitHub acquisition (soft-fail) | `backend/app/ai/artifacts/github_acquisition.py` |
| Verifier availability stub | `backend/app/ai/artifacts/verifier_status.py` |
| ORM | `backend/app/infrastructure/database/models/analysis_artifact_bundle.py` |
| Flags (default off) | `ARTIFACT_BUNDLE_ENABLED`, `ARTIFACT_PARSING_ENABLED`, `GITHUB_ARTIFACT_ACQUISITION_ENABLED`, `CAUSAL_ANALYSIS_ENABLED` in `.env.example` / `Settings` |
| Debug API | `GET /api/v1/analyses/{analysis_run_id}/artifact-bundle` |

**Still deferred (as of 6A.1):** later causal/verifier stages and Causal UI (see 6A.3 update below).

### Phase 6A.2 implementation references

| Deliverable | Location |
|-------------|----------|
| Migration `012_phase6a2_temporal_graph` | `backend/alembic/versions/012_phase6a2_temporal_graph.py` |
| Temporal domain | `backend/app/domain/temporal/` |
| Evidence graph domain | `backend/app/domain/evidence_graph/` |
| Temporal localizer | `backend/app/ai/temporal/` |
| Graph builder + consistency | `backend/app/ai/evidence_graph/` |
| Persist service | `backend/app/ai/evidence_graph/persist_service.py` |
| Debug APIs | `GET .../temporal-localisation`, `.../temporal-events`, `.../evidence-graph`, `.../graph-consistency` |
| Docs | `docs/PHASE6A_TEMPORAL_LOCALISATION.md`, `PHASE6A_EVIDENCE_GRAPH.md`, `PHASE6A_GRAPH_CONSISTENCY.md`, `PHASE6A_CAUSAL_AI_PIPELINE.md` |
| Flags | `TEMPORAL_LOCALISATION_ENABLED`, `EVIDENCE_GRAPH_ENABLED`, `GRAPH_CONSISTENCY_ENABLED` (default false) |

> **Update:** Phase 6A.2 delivered.

### Phase 6A.3 implementation references

| Deliverable | Location |
|-------------|----------|
| Audit | `docs/PHASE6A3_CLASSIFICATION_AUDIT.md` |
| Migration `013_phase6a3_hier_class` | `backend/alembic/versions/013_phase6a3_hier_class.py` |
| Taxonomy registry | `backend/app/domain/classification/` |
| Hierarchical orchestrator | `backend/app/ai/classification/hierarchical_orchestrator.py` |
| Open-set / disagreement / confidence | `open_set_detector.py`, `disagreement_analyzer.py`, `confidence_breakdown.py` |
| Debug APIs | hierarchical-classification, classification-candidates, open-set-assessment, classification-disagreement, classification-confidence, failure-taxonomy |
| Docs | `PHASE6A_HIERARCHICAL_CLASSIFICATION.md`, `PHASE6A_OPEN_SET_DETECTION.md`, `PHASE6A_CLASSIFICATION_DISAGREEMENT.md` |
| Flags | `HIERARCHICAL_CLASSIFICATION_ENABLED`, `OPEN_SET_DETECTION_ENABLED`, `CLASSIFICATION_DISAGREEMENT_ENABLED`, `CLASSIFICATION_CONFIDENCE_BREAKDOWN_ENABLED` (default false) |

> **Update:** Phase 6A.3 delivered.

### Phase 6A.4 implementation references

| Deliverable | Location |
|-------------|----------|
| Audit | `docs/PHASE6A4_HYPOTHESIS_AUDIT.md` |
| Migration `014_phase6a4_hypotheses` | `backend/alembic/versions/014_phase6a4_hypotheses.py` |
| Domain | `backend/app/domain/hypotheses/` |
| Generators / validators / critic | `backend/app/ai/hypotheses/` |
| Debug APIs | causal-hypotheses, hypothesis-generation-run, evidence, causal-path, critic |
| Docs | `PHASE6A_CAUSAL_HYPOTHESES.md`, templates/validation/critic docs |
| Flags | `CAUSAL_HYPOTHESIS_GENERATION_ENABLED`, `RULE_HYPOTHESIS_GENERATION_ENABLED`, `LLM_HYPOTHESIS_GENERATION_ENABLED`, `HYPOTHESIS_CRITIC_ENABLED` (default false) |

> **Update:** Phase 6A.4 delivered. Next approval ask is **Phase 6A.5** (hypothesis-directed RAG / ranking) only.

> **Update:** Phase 6A.5 Part 1A (audit) and **Part 1B** (hypothesis-directed retrieval infrastructure) delivered. Master flag `HYPOTHESIS_DIRECTED_RAG_ENABLED` defaults OFF. Causal ranking / Part 2+ still deferred.

**Still deferred:** 6A.6 Part 2 generation, 6A.7–6A.8 verifier/abstention stages, 6A.9 Causal UI.

> **Update:** Phase 6A.6 Part 1 counterfactual remediation foundation delivered (flags OFF; migration `016_phase6a6_cf_foundation`). Candidates only — no apply/verifiers. See `docs/PHASE6A6_COUNTERFACTUAL_REMEDIATION_FOUNDATION.md`.

---

## 17. Recommended next approval ask

> Approve Phase 6A.0 audit and authorise Phase 6A.1: IncidentArtifactBundle model, acquisition extensions (GitHub workflow YAML where permitted + manual bundle manifest), and artifact-specific parser interfaces — feature-flagged off by default — with migration `011_*` only if relational persistence is required in 6A.1 (otherwise JSON snapshot first).

> **Update:** Phase 6A.1–6A.4 and 6A.5 Part 1B delivered. Next approval ask is **Phase 6A.5 Part 2** (or ranking) only — do not start without separate approval.
## 18. References

- `docs/MASTER_ARCHITECTURE.md` § Phase 6 / Modules 8–10  
- `docs/AI_ARCHITECTURE.md`  
- `docs/DATABASE_ARCHITECTURE.md`  
- `docs/ARCHITECTURE_DECISION_LOG.md` (ADR-005, ADR-012, ADR-013)  
- `docs/PHASE5B_*`, `docs/PHASE5C_*`, `docs/PHASE5D_*`  
- `docs/EMBEDDING_SETUP.md`  
- `datasets/BENCHMARK_GUIDE.md`  
- Code: `backend/app/ai/orchestration/`, `backend/app/ai/rag/`, `backend/app/application/services/github_ingestion_service.py`, `backend/app/application/services/upload_service.py`, `frontend/src/pages/incidents/`
