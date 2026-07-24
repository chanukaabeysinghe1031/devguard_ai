"""Citation record: which knowledge chunks were used during an analysis run."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.analysis_run import AnalysisRun
    from app.infrastructure.database.models.knowledge_chunk import KnowledgeChunk


class RetrievedDocument(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Provides citation and grounding traceability for an analysis run."""

    __tablename__ = "retrieved_documents"

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    knowledge_chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    similarity_score: Mapped[float | None] = mapped_column(Numeric(7, 6), nullable=True)
    used_in_reasoning: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="retrieved_documents")
    knowledge_chunk: Mapped[KnowledgeChunk] = relationship(back_populates="retrievals")
