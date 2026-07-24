"""Retrievable documentation segment (metadata/reference; embeddings live in ChromaDB)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.knowledge_document import KnowledgeDocument
    from app.infrastructure.database.models.retrieved_document import RetrievedDocument


class KnowledgeChunk(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """A retrievable segment of a knowledge document.

    Embeddings may remain in ChromaDB; this table stores durable metadata and a
    reference to the vector store entry.
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (Index("ix_knowledge_chunks_document_id", "document_id"),)

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")
    retrievals: Mapped[list[RetrievedDocument]] = relationship(back_populates="knowledge_chunk")
