"""Ingest curated knowledge_base documents into PostgreSQL + vector store."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.rag.chunker import chunk_markdown
from app.ai.rag.metadata_enrichment import enrich_chunk_metadata
from app.domain.enums import KnowledgeDocumentStatus
from app.domain.interfaces.ai_providers import EmbeddedChunk, EmbeddingProvider, VectorStore
from app.domain.services.secret_masker import mask_secrets
from app.infrastructure.database.models.knowledge_chunk import KnowledgeChunk
from app.infrastructure.database.models.knowledge_document import KnowledgeDocument

logger = structlog.get_logger(__name__)


# Front-matter is optional YAML-like key: value lines after --- ... ---
def _parse_document(path: Path) -> tuple[dict[str, str], str]:
    raw = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {
        "provider": "general",
        "title": path.stem.replace("_", " ").title(),
        "source_url": "",
        "version": "1.0",
    }
    body = raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta[key.strip().lower()] = value.strip()
            body = parts[2].lstrip("\n")
    return meta, body


class KnowledgeIngestionService:
    """Idempotent ingestion of markdown docs into PG metadata + vector embeddings."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        knowledge_base_path: Path,
        lexical_retriever: Any | None = None,
    ) -> None:
        self._session = session
        self._embeddings = embedding_provider
        self._store = vector_store
        self._path = knowledge_base_path
        self._lexical = lexical_retriever

    async def ensure_indexed(self) -> int:
        if not self._path.exists():
            logger.warning("knowledge_base_missing", path=str(self._path))
            return 0

        indexed = 0
        for path in sorted(self._path.glob("**/*.md")):
            indexed += await self._ingest_file(path)
        await self._session.flush()
        await self._reindex_active_chunks()
        return indexed

    async def _ingest_file(self, path: Path) -> int:
        meta, body = _parse_document(path)
        # Secret masking MUST happen before hashing, chunking, and embedding.
        masked_body, _ = mask_secrets(body)
        content_hash = hashlib.sha256(masked_body.encode("utf-8")).hexdigest()

        stmt = (
            select(KnowledgeDocument)
            .where(KnowledgeDocument.content_hash == content_hash)
            .options(selectinload(KnowledgeDocument.chunks))
        )
        existing = await self._session.scalar(stmt)
        if existing is not None:
            return 0

        # Replace same title+provider if content changed.
        prior = await self._session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.provider == meta["provider"],
                KnowledgeDocument.title == meta["title"],
            )
        )
        if prior is not None:
            prior.status = KnowledgeDocumentStatus.ARCHIVED

        document = KnowledgeDocument(
            provider=meta["provider"],
            title=meta["title"],
            source_url=meta.get("source_url") or None,
            version=meta.get("version") or "1.0",
            content_hash=content_hash,
            status=KnowledgeDocumentStatus.ACTIVE,
            ingested_at=datetime.now(UTC),
        )
        self._session.add(document)
        await self._session.flush()

        seen_chunk_hashes: set[str] = set()
        for piece in chunk_markdown(masked_body):
            chunk_hash = hashlib.sha256(piece.content.encode("utf-8")).hexdigest()
            if chunk_hash in seen_chunk_hashes:
                continue
            seen_chunk_hashes.add(chunk_hash)
            enriched = enrich_chunk_metadata(
                base={
                    "provider": meta["provider"],
                    "title": meta["title"],
                    "source_url": meta.get("source_url") or "",
                    "document_status": "active",
                    "product": meta.get("product") or "",
                    "version": meta.get("version") or "1.0",
                },
                content=piece.content,
                heading=piece.heading,
                document_id=str(document.id),
                provider=meta["provider"],
                title=meta["title"],
                source_url=meta.get("source_url") or "",
                version=meta.get("version") or "1.0",
            )
            chunk = KnowledgeChunk(
                document_id=document.id,
                chunk_index=piece.index,
                heading=piece.heading,
                content=piece.content,
                token_count=piece.token_count,
                embedding_reference=None,
                chunk_metadata=enriched,
            )
            self._session.add(chunk)
        await self._session.flush()
        logger.info("knowledge_document_ingested", title=meta["title"], path=str(path.name))
        return 1

    async def _reindex_active_chunks(self) -> None:
        stmt = (
            select(KnowledgeChunk)
            .join(KnowledgeDocument)
            .where(KnowledgeDocument.status == KnowledgeDocumentStatus.ACTIVE)
            .options(selectinload(KnowledgeChunk.document))
        )
        chunks = list((await self._session.scalars(stmt)).all())
        if not chunks:
            return
        embedded = [
            EmbeddedChunk(
                chunk_id=str(chunk.id),
                text=chunk.content,
                metadata=_chunk_metadata(chunk),
            )
            for chunk in chunks
        ]
        vectors = self._embeddings.embed([c.text for c in embedded])
        self._store.upsert(embedded, vectors)
        if self._lexical is not None:
            self._lexical.index(embedded)
        for chunk in chunks:
            chunk.embedding_reference = f"{self._store.name}:{chunk.id}"


def _chunk_metadata(chunk: KnowledgeChunk) -> dict[str, Any]:
    meta = dict(chunk.chunk_metadata or {})
    return enrich_chunk_metadata(
        base=meta,
        content=chunk.content,
        heading=chunk.heading,
        document_id=str(chunk.document_id),
        chunk_id=str(chunk.id),
        provider=chunk.document.provider if chunk.document else meta.get("provider"),
        title=chunk.document.title if chunk.document else meta.get("title"),
        source_url=chunk.document.source_url if chunk.document else meta.get("source_url"),
        version=chunk.document.version if chunk.document else meta.get("version"),
    )


async def load_chunk_contents(
    session: AsyncSession,
    chunk_ids: list[UUID],
) -> dict[UUID, KnowledgeChunk]:
    if not chunk_ids:
        return {}
    rows = list(
        (
            await session.scalars(
                select(KnowledgeChunk)
                .where(KnowledgeChunk.id.in_(chunk_ids))
                .options(selectinload(KnowledgeChunk.document))
            )
        ).all()
    )
    return {row.id: row for row in rows}
