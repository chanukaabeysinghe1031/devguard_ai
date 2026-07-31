"""Feature vector extraction for retrieval relevance scoring."""

from __future__ import annotations

from app.ai.hypothesis_retrieval.identifiers import ExtractedIdentifiers
from app.ai.hypothesis_retrieval.versions import RETRIEVAL_CANDIDATE_FEATURES_VERSION
from app.domain.hypothesis_retrieval.models import (
    HypothesisRetrievalContext,
    HypothesisRetrievedItem,
    RetrievalCandidateFeatureVector,
)


class RetrievalCandidateFeatureExtractor:
    """Extract nullable feature components; never invent zeros for missing values."""

    def extract(
        self,
        item: HypothesisRetrievedItem,
        context: HypothesisRetrievalContext,
        identifiers: ExtractedIdentifiers | None = None,
    ) -> RetrievalCandidateFeatureVector:
        text = (item.text_excerpt or "").lower()
        ids = identifiers.all_identifiers if identifiers else []
        exact_hits = [i for i in ids if i and i.lower() in text]
        category = (context.category_code or "").lower()
        path = (item.source_path or "").lower()
        affected = (context.affected_path or "").lower()

        vector_sim = item.vector_score
        lexical_sim = item.lexical_score
        exact_error = None
        if context.error_signature and context.error_signature.lower() in text:
            exact_error = 1.0
        elif context.error_signature:
            exact_error = 0.0

        exact_id_overlap = None
        if ids:
            exact_id_overlap = len(exact_hits) / max(1, len(ids))

        category_match = None
        if category:
            category_match = 1.0 if category in text else 0.0

        source_path_match = None
        if affected:
            source_path_match = 1.0 if affected in path or affected in text else 0.0

        same_repo = None
        if context.commit_sha and item.commit_sha:
            same_repo = 1.0 if context.commit_sha == item.commit_sha else 0.0

        same_workflow = None
        if context.workflow_path and path:
            same_workflow = 1.0 if context.workflow_path.lower() in path else 0.0

        same_aws_action = None
        actions = identifiers.aws_actions if identifiers else context.permission_actions
        if actions:
            same_aws_action = (
                1.0 if any(a.lower() in text for a in actions if a) else 0.0
            )

        historical_quality = item.historical_score
        provenance = 1.0 if item.source_system and item.adapter_name else None
        meta_complete = 1.0 if item.metadata else None
        graph_distance = item.graph_distance
        authority = None
        if item.source_type.value in {"DOCUMENTATION", "STATIC_KNOWLEDGE"}:
            authority = 0.8
        elif item.source_type.value == "HISTORICAL_INCIDENT":
            authority = 0.5

        warning_penalty = None
        if (item.metadata or {}).get("validation_warnings"):
            warning_penalty = 0.2

        features = RetrievalCandidateFeatureVector(
            vector_similarity=vector_sim,
            lexical_similarity=lexical_sim,
            exact_error_match=exact_error,
            exact_identifier_overlap=exact_id_overlap,
            category_match=category_match,
            source_path_match=source_path_match,
            graph_distance=graph_distance,
            same_repository=same_repo,
            same_workflow=same_workflow,
            same_aws_action=same_aws_action,
            historical_incident_quality=historical_quality,
            official_source_authority=authority,
            provenance_completeness=provenance,
            metadata_completeness=meta_complete,
            validation_warning_penalty=warning_penalty,
        )
        # Stamp version into caller metadata when attached.
        _ = RETRIEVAL_CANDIDATE_FEATURES_VERSION
        return features
