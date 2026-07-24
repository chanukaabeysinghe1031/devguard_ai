"""Official documentation stored for retrieval-augmented generation (RAG)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import KnowledgeDocumentStatus
from app.infrastructure.database.base import (
    Base,
    UpdatedAtMixin,
    UUIDPrimaryKeyMixin,
)
from app.infrastructure.database.enums import knowledge_document_status_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.knowledge_chunk import KnowledgeChunk


class KnowledgeDocument(Base, UUIDPrimaryKeyMixin, UpdatedAtMixin):
    """A documentation source ingested for RAG (e.g. Terraform, AWS, Docker docs)."""

    __tablename__ = "knowledge_documents"

    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[KnowledgeDocumentStatus] = mapped_column(
        knowledge_document_status_enum,
        nullable=False,
        default=KnowledgeDocumentStatus.ACTIVE,
    )
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    chunks: Mapped[list[KnowledgeChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
