"""Knowledge base metadata — ``knowledge_documents`` and ``knowledge_chunks`` for
retrieval-augmented generation, plus the deferred
``retrieved_documents.knowledge_chunk_id`` foreign key.

Option B note
-------------
Additive wave. Vector embeddings continue to live in ChromaDB; PostgreSQL stores
only durable metadata and references. Under Option B the tables come up empty on
a recreated local database. The foreign key from ``retrieved_documents`` (created
in Migration 004) to ``knowledge_chunks`` is finalized here now that the target
table exists.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "006_knowledge_base_metadata"
down_revision: str | None = "005_reports_notifications_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

knowledge_document_status_enum = postgresql.ENUM(
    "active", "outdated", "archived", name="knowledge_document_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM("active", "outdated", "archived", name="knowledge_document_status").create(
        bind, checkfirst=True
    )

    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("version", sa.String(length=100), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            knowledge_document_status_enum,
            nullable=False,
            server_default=sa.text("'active'::knowledge_document_status"),
        ),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("embedding_reference", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])

    # Finalize the deferred FK from retrieved_documents (created in 004).
    op.create_foreign_key(
        "fk_retrieved_documents_knowledge_chunk_id",
        "retrieved_documents",
        "knowledge_chunks",
        ["knowledge_chunk_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_retrieved_documents_knowledge_chunk_id",
        "retrieved_documents",
        ["knowledge_chunk_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index("ix_retrieved_documents_knowledge_chunk_id", table_name="retrieved_documents")
    op.drop_constraint(
        "fk_retrieved_documents_knowledge_chunk_id",
        "retrieved_documents",
        type_="foreignkey",
    )

    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")

    postgresql.ENUM(name="knowledge_document_status").drop(bind, checkfirst=True)
