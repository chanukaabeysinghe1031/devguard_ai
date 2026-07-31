# Phase 6A.5 — Artifact Constraints

Version: `hypothesis_artifact_retrieval_v1`

`ArtifactRetrievalConstraints` prioritize affected artifact/path, changed files, workflow path, and commit metadata. Repository changes use `RepositoryChangeRetrievalAdapter` (context only — no full repo scan).
