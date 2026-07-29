"""Historical incident document indexing (org-scoped, no schema migration)."""

from __future__ import annotations

import hashlib
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from app.ai.orchestration.analysis_context import AnalysisContext, ClassificationCandidate
from app.ai.rag.models import HistoricalIncidentDocument
from app.ai.rag.signals import DiagnosticSignalExtractor
from app.domain.interfaces.ai_providers import EmbeddedChunk, EmbeddingProvider, VectorStore
from app.domain.services.secret_masker import mask_secrets

# Namespace for deterministic historical chunk IDs (not real knowledge_chunks FK).
_HISTORY_NS = uuid5(NAMESPACE_URL, "devguard-ai/historical-incident")


class HistoricalIncidentIndexService:
    """Idempotent in-memory/vector indexing of trusted resolved incidents.

    Documents are stored in the vector store with organisation_id metadata.
    They are NOT written as knowledge_chunks FK rows (no migration). Citations for
    historical hits are persisted only in analysis output_summary metadata.
    """

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        min_quality_score: float = 0.70,
    ) -> None:
        self._embeddings = embedding_provider
        self._store = vector_store
        self._min_quality = min_quality_score
        self._docs: dict[str, HistoricalIncidentDocument] = {}
        self._signals = DiagnosticSignalExtractor()

    @staticmethod
    def chunk_id_for(organisation_id: UUID, incident_id: UUID) -> UUID:
        return uuid5(_HISTORY_NS, f"{organisation_id}:{incident_id}")

    def index_resolved_incident(self, document: HistoricalIncidentDocument) -> str:
        if document.quality_score < self._min_quality:
            return "skipped_low_quality"
        text, _ = mask_secrets(document.indexed_text())
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        document.content_hash = content_hash
        key = f"{document.organisation_id}:{document.incident_id}"
        existing = self._docs.get(key)
        if existing is not None and existing.content_hash == content_hash:
            return "unchanged"

        chunk_uuid = self.chunk_id_for(document.organisation_id, document.incident_id)
        metadata = {
            "document_status": "active",
            "source_type": "historical_incident",
            "source_authority": "confirmed_resolved_incident",
            "organisation_id": str(document.organisation_id),
            "project_id": str(document.project_id) if document.project_id else "",
            "incident_id": str(document.incident_id),
            "title": document.title or "",
            "failure_categories": [document.confirmed_category],
            "technologies": list(document.technologies),
            "error_codes": list(document.error_codes),
            "pipeline_stages": [document.pipeline_stage] if document.pipeline_stage else [],
            "history_quality_score": document.quality_score,
            "content_hash": content_hash,
            "persist_citation": False,
            "resolved_at": document.resolved_at.isoformat() if document.resolved_at else "",
        }
        embedded = EmbeddedChunk(chunk_id=str(chunk_uuid), text=text, metadata=metadata)
        vector = self._embeddings.embed_documents([text])[0]
        self._store.upsert([embedded], [vector])
        self._docs[key] = document
        return "indexed" if existing is None else "reindexed"

    def reindex_incident(self, document: HistoricalIncidentDocument) -> str:
        return self.index_resolved_incident(document)

    def remove_incident(self, organisation_id: UUID, incident_id: UUID) -> bool:
        key = f"{organisation_id}:{incident_id}"
        removed = key in self._docs
        self._docs.pop(key, None)
        # Soft-invalidate via empty upsert with archived status (no delete API on store).
        chunk_uuid = self.chunk_id_for(organisation_id, incident_id)
        embedded = EmbeddedChunk(
            chunk_id=str(chunk_uuid),
            text="",
            metadata={
                "document_status": "archived",
                "source_type": "historical_incident",
                "organisation_id": str(organisation_id),
                "incident_id": str(incident_id),
                "persist_citation": False,
            },
        )
        vector = self._embeddings.embed_documents(["archived"])[0]
        self._store.upsert([embedded], [vector])
        return removed

    def backfill_resolved_incidents(
        self,
        documents: list[HistoricalIncidentDocument],
        *,
        organisation_id: UUID,
    ) -> int:
        """Organisation-scoped backfill only — never cross-org bulk."""
        count = 0
        for document in documents:
            if document.organisation_id != organisation_id:
                continue
            result = self.index_resolved_incident(document)
            if result in {"indexed", "reindexed"}:
                count += 1
        return count

    def build_document_from_resolution(
        self,
        *,
        incident_id: UUID,
        organisation_id: UUID,
        project_id: UUID | None,
        title: str | None,
        confirmed_category: str,
        root_cause_summary: str,
        resolution_summary: str,
        evidence_excerpts: list[str] | None = None,
        resolved_at: datetime | None = None,
        ai_recommendation_used: bool | None = None,
        has_resolution_steps: bool = False,
    ) -> HistoricalIncidentDocument:
        masked_root, _ = mask_secrets(root_cause_summary or "")
        masked_res, _ = mask_secrets(resolution_summary or "")
        evidence = []
        for excerpt in evidence_excerpts or []:
            masked, _ = mask_secrets(excerpt)
            evidence.append(masked[:180])
        # Conservative quality from available fields only — do not invent confirmation.
        quality = 0.55
        if confirmed_category and confirmed_category != "unknown_failure":
            quality += 0.15
        if masked_root.strip():
            quality += 0.10
        if masked_res.strip():
            quality += 0.10
        if has_resolution_steps:
            quality += 0.05
        if ai_recommendation_used is True:
            quality += 0.05
        quality = min(1.0, quality)

        # Extract tech/error codes from summaries via signal extractor on a stub context.
        stub = AnalysisContext(
            analysis_run_id=incident_id,
            incident_id=incident_id,
            combined_text=f"{masked_root}\n{masked_res}\n" + "\n".join(evidence),
            classifications=[
                ClassificationCandidate(
                    category_code=confirmed_category,
                    confidence=1.0,
                    rank=1,
                )
            ],
        )
        signals = self._signals.extract(stub)
        return HistoricalIncidentDocument(
            incident_id=incident_id,
            organisation_id=organisation_id,
            project_id=project_id,
            title=title,
            confirmed_category=confirmed_category,
            root_cause_summary=masked_root[:1000],
            resolution_summary=masked_res[:1000],
            technologies=list(signals.technologies),
            error_codes=list(signals.error_codes),
            pipeline_stage=signals.pipeline_stage,
            evidence_summary=evidence[:5],
            resolved_at=resolved_at,
            quality_score=round(quality, 4),
        )

    def list_for_org(self, organisation_id: UUID) -> list[HistoricalIncidentDocument]:
        return [doc for key, doc in self._docs.items() if key.startswith(f"{organisation_id}:")]
