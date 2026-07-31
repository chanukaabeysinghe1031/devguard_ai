"""Persist Part 3 assessments into existing JSONB (no migration 016)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.domain.evidence_assessment.models import EvidenceAssessmentRun
from app.infrastructure.database.models.hypothesis_retrieval import (
    HypothesisRetrievalRunRow,
    HypothesisRetrievalSessionRow,
)


class EvidenceAssessmentPersistService:
    """Merge evidence assessment payloads into retrieval run/session JSONB."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def persist(self, run: EvidenceAssessmentRun) -> None:
        if not run.retrieval_run_id:
            return
        org_id = UUID(run.organization_id)
        analysis_id = UUID(run.analysis_id)
        run_uuid = UUID(run.retrieval_run_id)

        row = await self._session.scalar(
            select(HypothesisRetrievalRunRow).where(
                HypothesisRetrievalRunRow.id == run_uuid,
                HypothesisRetrievalRunRow.organization_id == org_id,
                HypothesisRetrievalRunRow.analysis_run_id == analysis_id,
            )
        )
        if row is None:
            return

        snapshot = dict(row.configuration_snapshot or {})
        snapshot["evidence_assessment"] = {
            "assessment_version": run.assessment_version,
            "status": run.status,
            "configuration_snapshot": dict(run.configuration_snapshot),
            "ranking": run.ranking.to_dict() if run.ranking else None,
            "candidate_selection": (
                run.candidate_selection.to_dict() if run.candidate_selection else None
            ),
            "warnings": list(run.warnings),
            "limitations": list(run.limitations),
            "duration_ms": run.duration_ms,
            "summary": run.summary_dict(),
        }
        row.configuration_snapshot = snapshot
        flag_modified(row, "configuration_snapshot")

        sessions = list(
            (
                await self._session.scalars(
                    select(HypothesisRetrievalSessionRow).where(
                        HypothesisRetrievalSessionRow.retrieval_run_id == run_uuid,
                        HypothesisRetrievalSessionRow.organization_id == org_id,
                    )
                )
            ).all()
        )
        for sess in sessions:
            hid = str(sess.hypothesis_id)
            payload = run.hypothesis_assessments.get(hid)
            if payload is None:
                continue
            metrics: dict[str, Any] = dict(sess.metrics or {})
            metrics["evidence_assessment"] = payload
            sess.metrics = metrics
            flag_modified(sess, "metrics")

        await self._session.flush()
