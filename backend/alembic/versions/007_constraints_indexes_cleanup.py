"""Constraints, indexes, and cleanup — add the composite/partial/search indexes
recommended by DATABASE_ARCHITECTURE.md, and finalize obsolete-object cleanup.

Option B note
-------------
Final hardening wave. The destructive schema changes happened in Migrations
003–004; this wave is index/cleanup only and is intended to be the last (and
therefore the least reversible) step. Under Option B the local development
database is recreated empty, so the defensive ``DROP ... IF EXISTS`` and
``CREATE SEQUENCE IF NOT EXISTS`` statements below are idempotent no-ops on a
fresh database but keep the migration correct for any environment that still
carries legacy objects.
"""

from collections.abc import Sequence

from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "007_constraints_indexes_cleanup"
down_revision: str | None = "006_knowledge_base_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # ------------------------------------------------------------------
    # 1. Cleanup of obsolete legacy objects (all no-ops under Option B).
    # ------------------------------------------------------------------
    # analysis_history was removed in Migration 003; ensure it is gone.
    op.execute("DROP TABLE IF EXISTS analysis_history CASCADE")
    # The legacy user_role enum was dropped in Migration 002; ensure removal.
    postgresql.ENUM(name="user_role").drop(bind, checkfirst=True)
    # The incident_number sequence is created in Migration 003; ensure presence.
    op.execute("CREATE SEQUENCE IF NOT EXISTS incident_number_seq")

    # ------------------------------------------------------------------
    # 2. Partial index for open incidents (DATABASE_ARCHITECTURE §8).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_incidents_open
        ON incidents (project_id, severity, detected_at DESC)
        WHERE status IN ('detected', 'analysing', 'open', 'in_progress')
        """
    )

    # ------------------------------------------------------------------
    # 3. Full-text search index for incident titles / root-cause summaries.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_incidents_search
        ON incidents
        USING GIN (
            to_tsvector(
                'english',
                coalesce(title, '') || ' ' ||
                coalesce(description, '') || ' ' ||
                coalesce(root_cause_summary, '')
            )
        )
        """
    )

    # ------------------------------------------------------------------
    # 4. GIN index for searchable JSONB incident tags (DATABASE_ARCHITECTURE §8).
    # ------------------------------------------------------------------
    op.execute("CREATE INDEX IF NOT EXISTS ix_incidents_tags ON incidents USING GIN (tags)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_incidents_tags")
    op.execute("DROP INDEX IF EXISTS ix_incidents_search")
    op.execute("DROP INDEX IF EXISTS ix_incidents_open")
