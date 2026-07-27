"""Application service that executes queued analysis runs end-to-end."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestration.analysis_context import AnalysisContext, StageResult
from app.ai.orchestration.analysis_orchestrator import AnalysisOrchestrator, build_loaded_file
from app.core.config import Settings
from app.domain.enums import (
    AnalysisRunStatus,
    EvidenceType,
    IncidentStatus,
    ModelVersionStatus,
    RecommendationStepType,
    RiskLevel,
)
from app.domain.interfaces.storage_provider import FileStorage
from app.infrastructure.database.models.analysis_run import AnalysisRun
from app.infrastructure.database.models.evidence_item import EvidenceItem
from app.infrastructure.database.models.failure_category import FailureCategory
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.incident_event import IncidentEvent
from app.infrastructure.database.models.model_version import ModelVersion
from app.infrastructure.database.models.prediction import Prediction
from app.infrastructure.database.models.recommendation import Recommendation
from app.infrastructure.database.models.recommendation_step import RecommendationStep
from app.infrastructure.database.models.uploaded_file import UploadedFile

logger = structlog.get_logger(__name__)

RULES_MODEL_NAME = "rules-hybrid"
RULES_MODEL_VERSION = "1.0.0"


class AnalysisExecutionService:
    """Loads inputs, runs the orchestrator, and persists outputs transactionally."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        storage: FileStorage,
        orchestrator: AnalysisOrchestrator | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage = storage
        self._orchestrator = orchestrator or AnalysisOrchestrator()

    async def execute(self, analysis_run_id: UUID) -> None:
        run = await self._session.get(AnalysisRun, analysis_run_id)
        if run is None:
            logger.warning("analysis_run_missing", analysis_run_id=str(analysis_run_id))
            return
        if run.status != AnalysisRunStatus.QUEUED:
            logger.info(
                "analysis_run_skip",
                analysis_run_id=str(analysis_run_id),
                status=run.status.value,
            )
            return

        started = datetime.now(UTC)
        run.started_at = started
        run.status = AnalysisRunStatus.PREPROCESSING
        run.current_stage = "validating"
        run.progress_percentage = 1
        await self._set_incident_status(run.incident_id, IncidentStatus.ANALYSING)
        await self._session.flush()

        try:
            context = await self._build_context(run)

            async def on_progress(
                status: AnalysisRunStatus,
                stage: str,
                progress: int,
                stages: list[StageResult],
            ) -> None:
                await self._session.refresh(run)
                if run.status == AnalysisRunStatus.FAILED and run.error_code == "CANCELLED":
                    raise RuntimeError("CANCELLED")
                run.status = status
                run.current_stage = stage
                run.progress_percentage = progress
                run.output_summary = {
                    **(run.output_summary or {}),
                    "stages": [_stage_dict(s) for s in stages],
                    "partial": context.partial,
                    "warnings": context.warnings,
                }
                await self._session.flush()

            context = await self._orchestrator.run(context, on_progress=on_progress)
            await self._persist_results(run, context, started)
            await self._session.flush()
            logger.info("analysis_run_completed", analysis_run_id=str(analysis_run_id))
        except Exception as exc:
            if str(exc) == "CANCELLED":
                return
            run = await self._session.get(AnalysisRun, analysis_run_id)
            if run is None:
                return
            if run.status == AnalysisRunStatus.FAILED and run.error_code == "CANCELLED":
                return
            run.status = AnalysisRunStatus.FAILED
            run.current_stage = "failed"
            run.error_code = "ANALYSIS_FAILED"
            run.error_message = str(exc)[:1000]
            run.completed_at = datetime.now(UTC)
            if run.started_at:
                run.duration_ms = int((run.completed_at - run.started_at).total_seconds() * 1000)
            await self._set_incident_status(run.incident_id, IncidentStatus.ANALYSIS_FAILED)
            await self._record_event(
                incident_id=run.incident_id,
                title="AI analysis failed",
                description="The analysis pipeline failed.",
                event_type="analysis_failed",
                metadata={"analysis_run_id": str(run.id), "error_code": run.error_code},
            )
            await self._session.flush()
            logger.exception("analysis_run_failed", analysis_run_id=str(analysis_run_id))

    async def _build_context(self, run: AnalysisRun) -> AnalysisContext:
        input_summary = run.input_summary or {}
        file_id_strs = input_summary.get("file_ids") or []
        options = dict(input_summary.get("options") or {})
        # Settings override request flags for hard disable.
        if not self._settings.enable_rag:
            options["enable_rag"] = False
        if not self._settings.enable_llm:
            options["enable_llm"] = False

        file_ids = [UUID(str(fid)) for fid in file_id_strs]
        if file_ids:
            stmt = select(UploadedFile).where(
                UploadedFile.id.in_(file_ids),
                UploadedFile.incident_id == run.incident_id,
            )
        else:
            stmt = select(UploadedFile).where(UploadedFile.incident_id == run.incident_id)
        uploaded_files = list((await self._session.scalars(stmt)).all())
        if not uploaded_files:
            raise ValueError("No uploaded files found for this analysis run.")

        loaded = []
        for uploaded in uploaded_files:
            raw = await self._storage.read(relative_path=uploaded.storage_path)
            loaded.append(
                build_loaded_file(
                    file_id=uploaded.id,
                    original_filename=uploaded.original_filename,
                    file_type=uploaded.file_type,
                    raw_bytes=raw,
                    storage_path=uploaded.storage_path,
                )
            )

        return AnalysisContext(
            analysis_run_id=run.id,
            incident_id=run.incident_id,
            file_ids=[f.file_id for f in loaded],
            options=options,
            files=loaded,
        )

    async def _persist_results(
        self,
        run: AnalysisRun,
        context: AnalysisContext,
        started: datetime,
    ) -> None:
        model = await self._ensure_model_version()
        categories = await self._load_categories()

        primary_prediction: Prediction | None = None
        for candidate in context.classifications:
            category = categories.get(candidate.category_code) or categories.get("unknown_failure")
            if category is None:
                raise ValueError(f"Missing failure category '{candidate.category_code}'.")
            prediction = Prediction(
                analysis_run_id=run.id,
                failure_category_id=category.id,
                model_version_id=model.id,
                confidence=Decimal(str(candidate.confidence)),
                rank=candidate.rank,
                predicted_label=candidate.category_code,
                root_cause_summary=candidate.root_cause_summary,
                technical_explanation=candidate.technical_explanation,
                impact_summary=candidate.impact_summary,
                reasoning_metadata={
                    "matched_rules": candidate.matched_rules,
                    "engine": context.model_name,
                    "version": context.model_version,
                },
            )
            self._session.add(prediction)
            await self._session.flush()
            if candidate.rank == 1:
                primary_prediction = prediction

        for item in context.evidence:
            try:
                evidence_type = EvidenceType(item.evidence_type)
            except ValueError:
                evidence_type = EvidenceType.LOG_LINE
            self._session.add(
                EvidenceItem(
                    analysis_run_id=run.id,
                    prediction_id=primary_prediction.id if primary_prediction else None,
                    uploaded_file_id=item.uploaded_file_id,
                    evidence_type=evidence_type,
                    raw_excerpt=item.raw_excerpt,
                    normalized_excerpt=item.normalized_excerpt,
                    source_name=item.source_name,
                    line_start=item.line_start,
                    line_end=item.line_end,
                    explanation=item.explanation,
                    importance_score=Decimal(str(item.importance_score)),
                    evidence_metadata=item.metadata,
                )
            )

        if context.recommendation is not None and primary_prediction is not None:
            recommendation = Recommendation(
                analysis_run_id=run.id,
                prediction_id=primary_prediction.id,
                root_cause_summary=context.recommendation.root_cause_summary,
                explanation=context.recommendation.explanation,
                confidence_score=Decimal(str(context.recommendation.confidence_score)),
                llm_model=context.recommendation.llm_model,
            )
            self._session.add(recommendation)
            await self._session.flush()
            for step in context.recommendation.steps:
                try:
                    step_type = RecommendationStepType(step.step_type)
                except ValueError:
                    step_type = RecommendationStepType.REMEDIATION
                risk = None
                if step.risk_level:
                    try:
                        risk = RiskLevel(step.risk_level)
                    except ValueError:
                        risk = RiskLevel.LOW
                self._session.add(
                    RecommendationStep(
                        recommendation_id=recommendation.id,
                        analysis_run_id=run.id,
                        step_number=step.step_number,
                        step_type=step_type,
                        title=step.title,
                        action=step.action,
                        explanation=step.explanation,
                        expected_result=step.expected_result,
                        risk_level=risk,
                        difficulty=step.difficulty,
                        command_template=step.command_template,
                        completed=False,
                    )
                )

        completed = datetime.now(UTC)
        run.status = AnalysisRunStatus.COMPLETED
        run.current_stage = "completed"
        run.progress_percentage = 100
        run.completed_at = completed
        run.duration_ms = int((completed - started).total_seconds() * 1000)
        run.error_code = None
        run.error_message = None
        primary = context.classifications[0] if context.classifications else None
        run.output_summary = {
            "partial": context.partial,
            "warnings": context.warnings,
            "input_type": context.input_type,
            "signals": context.signals,
            "stages": [_stage_dict(s) for s in context.stages],
            "classification": (
                {
                    "category": primary.category_code,
                    "confidence": primary.confidence,
                    "rank": primary.rank,
                }
                if primary
                else None
            ),
            "root_cause_summary": primary.root_cause_summary if primary else None,
            "evidence_count": len(context.evidence),
            "recommendation_count": (
                1 if context.recommendation is not None else 0
            ),
            "model_versions": {
                "classifier": f"{context.model_name}-{context.model_version}",
                "reasoning": "template" if not context.enable_llm else "llm",
            },
        }
        await self._set_incident_status(run.incident_id, IncidentStatus.OPEN)
        await self._record_event(
            incident_id=run.incident_id,
            title="AI analysis completed",
            description=(
                primary.root_cause_summary
                if primary
                else "Analysis completed."
            ),
            event_type="analysis_completed",
            metadata={
                "analysis_run_id": str(run.id),
                "category": primary.category_code if primary else None,
                "confidence": primary.confidence if primary else None,
            },
        )

    async def _ensure_model_version(self) -> ModelVersion:
        stmt = select(ModelVersion).where(
            ModelVersion.model_name == RULES_MODEL_NAME,
            ModelVersion.version == RULES_MODEL_VERSION,
        )
        existing = await self._session.scalar(stmt)
        if existing is not None:
            return existing
        model = ModelVersion(
            model_name=RULES_MODEL_NAME,
            model_type="rules_hybrid",
            version=RULES_MODEL_VERSION,
            provider="devguard",
            status=ModelVersionStatus.ACTIVE,
            configuration={"engine": "rules+keywords", "llm": False},
            metrics={"deterministic": True},
            trained_at=datetime.now(UTC),
        )
        self._session.add(model)
        await self._session.flush()
        return model

    async def _load_categories(self) -> dict[str, FailureCategory]:
        rows = list((await self._session.scalars(select(FailureCategory))).all())
        return {row.code: row for row in rows}

    async def _set_incident_status(
        self,
        incident_id: UUID,
        status: IncidentStatus,
    ) -> None:
        incident = await self._session.get(Incident, incident_id)
        if incident is None:
            return
        # Do not regress terminal human statuses unexpectedly.
        if incident.status in {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}:
            return
        incident.status = status

    async def _record_event(
        self,
        *,
        incident_id: UUID,
        title: str,
        description: str | None,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            IncidentEvent(
                incident_id=incident_id,
                event_type=event_type,
                actor_type="ai",
                actor_user_id=None,
                title=title,
                description=description,
                event_metadata=metadata,
                occurred_at=datetime.now(UTC),
            )
        )


def _stage_dict(stage: StageResult) -> dict[str, Any]:
    return {
        "name": stage.name,
        "status": stage.status,
        "duration_ms": stage.duration_ms,
        "detail": stage.detail,
    }
