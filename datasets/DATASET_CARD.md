# Dataset Card — DevGuard AI Corpus (Phase 1)

**Version:** see `datasets/VERSION`  
**Status:** collection scaffolding (not a released evaluation corpus)  
**Owner:** DevGuard AI MSc project

## 1. Motivation

Support academically rigorous CI/CD incident intelligence by building a retrieval knowledge base from **real public DevOps incidents** (GitHub Issues API) plus a later layer of **official documentation**, rather than hand-writing dozens of synthetic knowledge pages as the primary corpus.

## 2. Intended uses

- RAG knowledge indexing (after curation, chunking, embedding)
- Retrieval evaluation (Precision@5, Recall@5, MRR, nDCG)
- Classification / hybrid-retrieval research comparisons

**Out of scope for this card version:** production customer log sharing; OpenAI training.

## 3. Separation of concerns

| Corpus | Purpose |
|--------|---------|
| Failure / benchmark dataset | Labels, queries, gold relevant chunks |
| RAG knowledge base | Indexed chunks for diagnosis |
| `knowledge_base/*.md` | Small curated enrichment only |

## 4. Data sources (planned)

- Public GitHub issues from curated repositories (`manifests/collection_targets.json`)
- Official documentation (AWS, Docker, Terraform, GitHub Actions, Kubernetes) — later phase
- Controlled reproductions / synthetic samples only as minority supplements (`docs/DATASET_SPECIFICATION.md`)

## 5. Collection method

- GitHub REST API only (`scripts/dataset/collect_github_issues.py`)
- Prefer `state=closed` and bug-related labels
- Pull requests excluded
- Secret masking applied at collection time via DevGuard `mask_secrets`
- Provenance recorded per incident (`source_url`, `collection_date`, license/usage basis)

## 6. Target size

**300–600** curated resolved incidents for the MSc demonstration corpus (easier to clean, index, and manually verify than bulk repository dumps).

## 7. Labels / taxonomy

`failure_category` must use the frozen DevGuard codes:

`build_failure`, `test_failure`, `dependency_failure`, `configuration_failure`, `terraform_failure`, `docker_failure`, `deployment_failure`, `aws_permission_failure`, `network_failure`, `security_misconfiguration`, `unknown_failure`.

## 8. Risks and limitations

- GitHub issues vary in quality; many lack a clear resolution
- Suggested `failure_category` from collection targets is heuristic until human curation
- Character-bounded cleaning is not full NLP normalisation
- License/ToS compliance remains the collector’s responsibility for redistribution

## 9. Ethical / legal

- Do not collect private repositories or authenticated org-only data without permission
- Never commit tokens or unmasked secrets
- Prefer linking to public issue URLs over republishing large copyrighted doc mirrors without need

## 10. Maintenance

| Field | Value |
|-------|-------|
| Schema | `datasets/schemas/incident.schema.json` |
| Validator | `scripts/dataset/validate_incidents.py` |
| Next phases | official documentation enrichment (`0.5.0-official-docs`) complete; curated runbooks remain future |
