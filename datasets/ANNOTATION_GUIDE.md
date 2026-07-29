# Annotation / Curation Guide — Phases 1–3

## Phase 2 automatic cleaning

`scripts/dataset/clean_incidents.py` normalises text, re-masks secrets, and rejects spam / short / duplicate items into `datasets/sanitized/`.

## Phase 3 automatic knowledge extraction

`scripts/dataset/extract_knowledge.py` (heuristic_v1):

- Parses GitHub issue template sections (`What happened?`, `Actual Behavior`, `Expected Behavior`, `Workaround`, …)
- Fills `symptoms`, and when possible `root_cause` / `resolution`
- Refines `failure_category` with keyword rules (frozen taxonomy only)
- Writes:
  - `collection.status=curated` for high-confidence closed issues
  - `curation_candidate` for the rest (including all open issues)
  - Knowledge JSON under `datasets/processed/knowledge/`

Auto-curated counts are usually below the full 300–600 target because many GitHub bug reports never state a fix in the opening post. Promote strong **candidates** during light human review.

## Human promotion (optional before Phase 4 chunking)

On promotion from `curation_candidate` → `curated`:

1. Confirm `technology`
2. Confirm `failure_category` (frozen taxonomy only)
3. Edit `symptoms` / `root_cause` / `resolution` if needed
4. Set `collection.status` = `curated`
5. Set `provenance.modified` = true

## Reject when

- Spam / +1 / empty narrative
- Pure feature requests with no failure signal
- Secrets that cannot be safely removed
- Near-duplicates

## Do not

- Invent categories outside the frozen list
- Treat open issues as primary RAG knowledge without a clear resolution
- Call external LLMs on unredacted raw text
- Mix evaluation queries into the knowledge corpus without retrieval-query records
