"""Application service that executes queued analysis runs end-to-end."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import (
    build_analyzer,
    build_hybrid_pipeline,
    build_routing_policy,
)
from app.ai.orchestration.adaptive_router import AdaptiveExecutionRouter
from app.ai.orchestration.analysis_context import AnalysisContext, StageResult
from app.ai.orchestration.analysis_orchestrator import AnalysisOrchestrator, build_loaded_file
from app.ai.orchestration.models import ExecutionMode, parse_execution_mode
from app.ai.orchestration.policy import RoutingPolicyConfig
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
from app.infrastructure.database.models.retrieved_document import RetrievedDocument
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
            orchestrator = await self._build_ai_orchestrator(context)

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

            context = await orchestrator.run(context, on_progress=on_progress)
            await self._maybe_persist_artifact_bundle(run, context)
            await self._maybe_run_phase6a3(run, context)
            await self._maybe_run_phase6a4(run, context)
            await self._maybe_run_phase6a5_hypothesis_retrieval(run, context)
            await self._maybe_run_phase6a5_evidence_assessment(run, context)
            await self._maybe_run_phase6a6_counterfactual_foundation(run, context)
            await self._maybe_run_phase6a6_counterfactual_generation(run, context)
            await self._maybe_run_phase6a6_verifier_engine(run, context)
            await self._maybe_run_phase6a7_final_decision(run, context)
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
            incident = await self._session.get(Incident, run.incident_id)
            if incident is not None:
                from app.application.services.notification_service import NotificationService

                await NotificationService(self._session).notify_analysis_failed(
                    incident=incident,
                    requested_by=run.requested_by,
                    error_message=run.error_message,
                )
            await self._session.flush()
            logger.exception("analysis_run_failed", analysis_run_id=str(analysis_run_id))

    async def _build_context(self, run: AnalysisRun) -> AnalysisContext:
        input_summary = run.input_summary or {}
        file_id_strs = input_summary.get("file_ids") or []
        options = dict(input_summary.get("options") or {})
        options.setdefault("execution_mode", self._settings.default_execution_mode)
        if self._settings.default_budget_usd is not None:
            options.setdefault("budget_usd", str(self._settings.default_budget_usd))
        options.setdefault("latency_limit_ms", self._settings.default_latency_limit_ms)
        options.setdefault("risk_level", "medium")
        options["llm_provider"] = self._settings.llm_provider
        if self._settings.llm_input_cost_usd_per_million_tokens is not None:
            options["llm_input_cost_usd_per_million_tokens"] = str(
                self._settings.llm_input_cost_usd_per_million_tokens
            )
        if self._settings.llm_output_cost_usd_per_million_tokens is not None:
            options["llm_output_cost_usd_per_million_tokens"] = str(
                self._settings.llm_output_cost_usd_per_million_tokens
            )
        if self._settings.embedding_cost_usd_per_million_tokens is not None:
            options["embedding_cost_usd_per_million_tokens"] = str(
                self._settings.embedding_cost_usd_per_million_tokens
            )

        # Server feature flags cannot be bypassed by request options.
        if not self._settings.enable_rag:
            options["enable_rag"] = False
        if not self._settings.enable_llm:
            options["enable_llm"] = False
        if (
            not self._settings.enable_confidence_routing
            and options.get("execution_mode") == ExecutionMode.CONFIDENCE_ROUTED.value
        ):
            options["execution_mode"] = ExecutionMode.RAG_LLM.value
        if (
            not self._settings.enable_historical_retrieval
            and options.get("retrieval_mode") == "hybrid_with_history"
        ):
            options["retrieval_mode"] = "hybrid_static"
        if not self._settings.enable_hybrid_retrieval:
            options["retrieval_mode"] = "embedding_only"
        if "retrieval_mode" not in options:
            options["retrieval_mode"] = self._settings.default_retrieval_mode

        # Phase 6A.6 — request options cannot force counterfactual flags ON.
        if not self._settings.counterfactual_remediation_enabled:
            options["counterfactual_remediation_enabled"] = False
        if not self._settings.counterfactual_constraint_extraction_enabled:
            options["counterfactual_constraint_extraction_enabled"] = False
        if not self._settings.minimal_change_planning_enabled:
            options["minimal_change_planning_enabled"] = False
        if not self._settings.counterfactual_template_registry_enabled:
            options["counterfactual_template_registry_enabled"] = False
        if not self._settings.counterfactual_persistence_enabled:
            options["counterfactual_persistence_enabled"] = False
        if not self._settings.rule_remediation_generation_enabled:
            options["rule_remediation_generation_enabled"] = False
        if not self._settings.llm_remediation_generation_enabled:
            options["llm_remediation_generation_enabled"] = False
        if not self._settings.remediation_risk_analysis_enabled:
            options["remediation_risk_analysis_enabled"] = False
        if not self._settings.remediation_side_effect_analysis_enabled:
            options["remediation_side_effect_analysis_enabled"] = False
        if not self._settings.remediation_ranking_enabled:
            options["remediation_ranking_enabled"] = False
        if not self._settings.remediation_deduplication_enabled:
            options["remediation_deduplication_enabled"] = False
        if not self._settings.remediation_diversity_enabled:
            options["remediation_diversity_enabled"] = False
        if not self._settings.remediation_patch_rendering_enabled:
            options["remediation_patch_rendering_enabled"] = False
        if not self._settings.remediation_rollback_generation_enabled:
            options["remediation_rollback_generation_enabled"] = False
        if not self._settings.remediation_reference_validation_enabled:
            options["remediation_reference_validation_enabled"] = False
        if not self._settings.remediation_constraint_validation_enabled:
            options["remediation_constraint_validation_enabled"] = False
        # Phase 6A.6 Part 3 — request options cannot force verifier flags ON.
        if not self._settings.verifier_engine_enabled:
            options["verifier_engine_enabled"] = False
        if not self._settings.terraform_verifier_enabled:
            options["terraform_verifier_enabled"] = False
        if not self._settings.actionlint_verifier_enabled:
            options["actionlint_verifier_enabled"] = False
        if not self._settings.checkov_verifier_enabled:
            options["checkov_verifier_enabled"] = False
        if not self._settings.opa_verifier_enabled:
            options["opa_verifier_enabled"] = False
        if not self._settings.security_verifier_enabled:
            options["security_verifier_enabled"] = False
        if not self._settings.verifier_persistence_enabled:
            options["verifier_persistence_enabled"] = False

        # Clamp latency to server maximum.
        try:
            requested_latency = int(options.get("latency_limit_ms") or 0)
            options["latency_limit_ms"] = min(
                requested_latency,
                self._settings.max_latency_limit_ms,
            )
        except (TypeError, ValueError):
            options["latency_limit_ms"] = self._settings.default_latency_limit_ms

        incident = await self._session.get(Incident, run.incident_id)
        organization_id = None
        if incident is not None:
            options["server_risk_level"] = incident.severity.value
            options["project_id"] = str(incident.project_id)
            from app.infrastructure.database.models.project import Project

            project = await self._session.get(Project, incident.project_id)
            if project is not None:
                organization_id = project.organization_id
                options["organisation_id"] = str(project.organization_id)

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

        mode = parse_execution_mode(options.get("execution_mode"))
        return AnalysisContext(
            analysis_run_id=run.id,
            incident_id=run.incident_id,
            organization_id=organization_id,
            file_ids=[f.file_id for f in loaded],
            options=options,
            files=loaded,
            requested_execution_mode=mode,
            execution_mode=mode.value,
            effective_execution_mode=mode.value,
        )

    async def _build_ai_orchestrator(self, context: AnalysisContext) -> AnalysisOrchestrator:
        policy = build_routing_policy(self._settings)
        policy = RoutingPolicyConfig(
            **{
                **policy.__dict__,
                "enable_rag": bool(context.options.get("enable_rag", False)) and policy.enable_rag,
                "enable_llm": bool(context.options.get("enable_llm", False)) and policy.enable_llm,
            }
        )
        retriever = None
        hybrid_retrieval = None
        analyzer = None
        mode = parse_execution_mode(context.options.get("execution_mode"))
        may_need_rag = mode in {
            ExecutionMode.RULES_RAG,
            ExecutionMode.RAG_LLM,
            ExecutionMode.CONFIDENCE_ROUTED,
        } and bool(context.options.get("enable_rag", False))
        may_need_llm = mode in {
            ExecutionMode.LLM_ONLY,
            ExecutionMode.RAG_LLM,
            ExecutionMode.CONFIDENCE_ROUTED,
        } and bool(context.options.get("enable_llm", False))
        if may_need_rag:
            retriever, hybrid_retrieval = await build_hybrid_pipeline(self._session, self._settings)
        if may_need_llm:
            analyzer = build_analyzer(self._settings)
        return AnalysisOrchestrator(
            retriever=retriever,
            hybrid_retrieval=hybrid_retrieval,
            root_cause_analyzer=analyzer,
            policy=policy,
            router=AdaptiveExecutionRouter(policy),
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
                    "grounding_valid": context.grounding_valid,
                    "reasoning_provider": context.reasoning_provider_name,
                    "llm_root_cause": context.llm_root_cause if candidate.rank == 1 else None,
                    "fusion": context.fusion_result.to_dict() if context.fusion_result else None,
                    "final_confidence": (
                        context.final_confidence_assessment.to_dict()
                        if context.final_confidence_assessment
                        else None
                    ),
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

        for chunk in context.retrieved_chunks:
            meta = getattr(chunk, "metadata", None) or {}
            # Historical hits are not knowledge_chunks FK rows — skip relational citation.
            if meta.get("persist_citation") is False:
                continue
            if str(meta.get("source_type") or "") == "historical_incident":
                continue
            self._session.add(
                RetrievedDocument(
                    analysis_run_id=run.id,
                    knowledge_chunk_id=chunk.chunk_id,
                    rank=chunk.rank,
                    similarity_score=Decimal(str(round(chunk.similarity_score, 6))),
                    used_in_reasoning=bool(chunk.used_in_reasoning),
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
            "recommendation_count": (1 if context.recommendation is not None else 0),
            "retrieval_query": context.retrieval_query or None,
            "retrieved_count": len(context.retrieved_chunks),
            "grounding_valid": context.grounding_valid,
            "execution_mode": context.requested_execution_mode.value,
            "effective_execution_mode": context.effective_execution_mode,
            "routing_decision": context.routing_decision,
            "initial_routing_decision": (
                context.initial_routing_decision.to_dict()
                if context.initial_routing_decision
                else None
            ),
            "post_retrieval_routing_decision": (
                context.post_retrieval_routing_decision.to_dict()
                if context.post_retrieval_routing_decision
                else None
            ),
            "confidence_metrics": (
                context.confidence_assessment.to_dict()
                if context.confidence_assessment
                else context.confidence_metrics
            ),
            "evidence_quality": (
                context.evidence_quality_assessment.to_dict()
                if context.evidence_quality_assessment
                else None
            ),
            "uncertainty": (
                context.uncertainty_assessment.to_dict() if context.uncertainty_assessment else None
            ),
            "retrieval_quality": (
                context.retrieval_quality_assessment.to_dict()
                if context.retrieval_quality_assessment
                else None
            ),
            "final_confidence": (
                context.final_confidence_assessment.to_dict()
                if context.final_confidence_assessment
                else None
            ),
            "fusion": context.fusion_result.to_dict() if context.fusion_result else None,
            "cost_metrics": context.cost_metrics,
            "budget": context.budget.to_dict() if context.budget else None,
            "budget_usage": context.budget_usage.to_dict() if context.budget_usage else None,
            "provider_usage": [item.to_dict() for item in context.provider_usage],
            "fallback_used": context.fallback_used,
            "fallback_reason": context.fallback_reason,
            "evaluation_metadata": context.evaluation_metadata,
            "retrieval_mode": context.options.get("retrieval_mode"),
            "retrieval_configuration_hash": context.options.get("retrieval_configuration_hash"),
            "retrieval_weight_profile": context.options.get("retrieval_weight_profile"),
            "retrieval_result": context.options.get("retrieval_result"),
            "artifact_bundle": context.options.get("artifact_bundle"),
            "temporal_localisation": context.options.get("temporal_localisation"),
            "evidence_graph": context.options.get("evidence_graph"),
            "hierarchical_classification": context.options.get("hierarchical_classification"),
            "causal_hypotheses": context.options.get("causal_hypotheses"),
            "final_diagnosis": context.options.get("final_diagnosis"),
            "model_versions": {
                "classifier": f"{context.model_name}-{context.model_version}",
                "reasoning": context.reasoning_provider_name
                or ("template" if not context.enable_llm else "llm"),
                "retrieval": context.retrieval_backend,
                "embedding": context.embedding_provider_name,
            },
        }
        await self._set_incident_status(run.incident_id, IncidentStatus.OPEN)
        await self._record_event(
            incident_id=run.incident_id,
            title="AI analysis completed",
            description=(primary.root_cause_summary if primary else "Analysis completed."),
            event_type="analysis_completed",
            metadata={
                "analysis_run_id": str(run.id),
                "category": primary.category_code if primary else None,
                "confidence": primary.confidence if primary else None,
            },
        )
        incident = await self._session.get(Incident, run.incident_id)
        if incident is not None:
            from app.application.services.notification_service import NotificationService

            await NotificationService(self._session).notify_analysis_completed(
                incident=incident,
                requested_by=run.requested_by,
                category=primary.category_code if primary else None,
                root_cause=primary.root_cause_summary if primary else None,
            )
        logger.info(
            "analysis_observability_summary",
            analysis_run_id=str(run.id),
            incident_id=str(run.incident_id),
            requested_by=str(run.requested_by),
            project_id=str(context.options.get("project_id") or ""),
            classification=(primary.category_code if primary else None),
            confidence=(primary.confidence if primary else None),
            retrieval_latency_ms=next(
                (s.duration_ms for s in context.stages if s.name == "retrieving_knowledge"),
                None,
            ),
            reasoning_latency_ms=next(
                (s.duration_ms for s in context.stages if s.name == "reasoning"),
                None,
            ),
            total_latency_ms=run.duration_ms,
            provider=context.reasoning_provider_name,
            model=context.reasoning_provider_name,
            token_usage=(context.signals or {}).get("reasoning_usage"),
            estimated_cost=context.cost_metrics,
            retrieved_document_count=len(context.retrieved_chunks),
            warnings=context.warnings,
            errors=(run.error_message if run.status == AnalysisRunStatus.FAILED else None),
        )

    async def _maybe_persist_artifact_bundle(
        self,
        run: AnalysisRun,
        context: AnalysisContext,
    ) -> None:
        """Build/persist Phase 6A artifact bundle when enabled. Soft-fail only."""
        need_bundle = bool(self._settings.artifact_bundle_enabled)
        need_6a2 = bool(
            self._settings.temporal_localisation_enabled
            or self._settings.evidence_graph_enabled
        )
        if not need_bundle and not need_6a2:
            return
        try:
            from app.ai.artifacts.bundle_service import ArtifactBundleService

            incident = await self._session.get(Incident, run.incident_id)
            if incident is None or context.organization_id is None:
                return

            stmt = select(UploadedFile).where(UploadedFile.incident_id == run.incident_id)
            if context.file_ids:
                stmt = stmt.where(UploadedFile.id.in_(context.file_ids))
            uploaded_files = list((await self._session.scalars(stmt)).all())
            file_contents: dict[UUID, str] = {}
            for uploaded in uploaded_files:
                raw = await self._storage.read(relative_path=uploaded.storage_path)
                try:
                    file_contents[uploaded.id] = raw.decode("utf-8")
                except UnicodeDecodeError:
                    file_contents[uploaded.id] = raw.decode("utf-8", errors="replace")

            tags = incident.tags if isinstance(incident.tags, dict) else {}
            github_raw = tags.get("github")
            github: dict[str, Any] = github_raw if isinstance(github_raw, dict) else {}
            bundle_ctx = {
                "provider": "github" if github else "upload",
                "repository": github.get("repository_full_name"),
                "commit_sha": None,
                "branch": None,
                "workflow_name": github.get("workflow_name"),
                "workflow_run_id": github.get("run_id"),
                "workflow_run_attempt": github.get("run_attempt"),
            }

            service = ArtifactBundleService(self._session, self._settings)
            bundle = await service.build_from_uploaded_files(
                organization_id=context.organization_id,
                incident_id=run.incident_id,
                project_id=incident.project_id,
                pipeline_run_id=incident.pipeline_run_id,
                analysis_run_id=run.id,
                files=uploaded_files,
                file_contents=file_contents,
                context=bundle_ctx,
            )
            # 6A.2 needs structured parse entities even if ARTIFACT_PARSING_ENABLED is off.
            parse_results: dict[str, list[Any]] = {}
            if service.parsing_enabled() or need_6a2:
                from app.ai.artifacts.parsers.registry import build_default_parser_registry

                registry = build_default_parser_registry()
                for artifact in bundle.artifacts:
                    if not artifact.content:
                        continue
                    parse_results[artifact.id] = registry.parse_all(
                        artifact.content,
                        filename=artifact.filename,
                        kind=artifact.kind,
                    )

            row = None
            if need_bundle:
                row = await service.persist_bundle(
                    bundle,
                    parse_results if service.parsing_enabled() else {},
                )
                context.options["artifact_bundle"] = {
                    "bundle_id": str(row.id),
                    "available_artifacts": list(bundle.available_artifacts),
                    "missing_artifacts": list(bundle.missing_artifacts),
                    "artifact_count": len(bundle.artifacts),
                    "parse_result_count": sum(len(v) for v in parse_results.values()),
                    "collection_error_count": len(bundle.artifact_collection_errors),
                }
            bundle_id = row.id if row is not None else None
            await self._maybe_run_phase6a2(
                run=run,
                context=context,
                incident=incident,
                bundle=bundle,
                bundle_id=bundle_id,
                parse_results=parse_results,
            )
        except Exception as exc:  # noqa: BLE001 - never fail analysis for bundle issues
            logger.warning(
                "artifact_bundle_persist_failed",
                analysis_run_id=str(run.id),
                error=type(exc).__name__,
            )
            context.warnings.append(f"artifact_bundle_failed:{type(exc).__name__}")
            context.options["artifact_bundle"] = {
                "error": type(exc).__name__,
                "enabled": True,
            }

    async def _maybe_run_phase6a2(
        self,
        *,
        run: AnalysisRun,
        context: AnalysisContext,
        incident: Incident,
        bundle: Any,
        bundle_id: UUID | None,
        parse_results: dict[str, list[Any]],
    ) -> None:
        """Temporal localisation + evidence graph. Soft-fail; does not alter diagnosis."""
        temporal_on = bool(self._settings.temporal_localisation_enabled)
        graph_on = bool(self._settings.evidence_graph_enabled)
        consistency_on = bool(self._settings.graph_consistency_enabled)
        if not temporal_on and not graph_on:
            return
        if context.organization_id is None:
            return

        try:
            from app.ai.evidence_graph.builder import CrossArtifactEvidenceGraphBuilder
            from app.ai.evidence_graph.consistency import GraphConsistencyEngine
            from app.ai.evidence_graph.persist_service import Phase6A2PersistService
            from app.ai.temporal.localizer import TemporalRootCauseLocalizer

            persist = Phase6A2PersistService(self._session, self._settings)
            temporal_result = None
            bundle_id_str = str(bundle_id) if bundle_id else None
            if temporal_on:
                localizer = TemporalRootCauseLocalizer(
                    max_events=self._settings.temporal_max_events
                )
                temporal_result = localizer.localize(
                    analysis_id=str(run.id),
                    organization_id=str(context.organization_id),
                    project_id=str(incident.project_id) if incident.project_id else None,
                    artifact_bundle_id=bundle_id_str,
                    parse_by_artifact=parse_results,
                    workflow_name=getattr(bundle, "workflow_name", None),
                    enabled=True,
                )
                temporal_result.organization_id = str(context.organization_id)
                temporal_result.incident_id = str(run.incident_id)
                await persist.persist_temporal(temporal_result)
                context.options["temporal_localisation"] = {
                    "status": temporal_result.status.value,
                    "primary_failure_event_id": temporal_result.primary_failure_event_id,
                    "primary_failure_type": temporal_result.primary_failure_type,
                    "confidence": temporal_result.confidence,
                    "ordering_method": temporal_result.ordering_method.value,
                    "event_count": len(temporal_result.events),
                    "warnings": list(temporal_result.warnings),
                }
                await self._record_event(
                    incident_id=run.incident_id,
                    title="Temporal localisation completed",
                    description=(
                        temporal_result.primary_failure_summary
                        or temporal_result.status.value
                    ),
                    event_type="temporal_localisation_completed",
                    metadata={
                        "analysis_run_id": str(run.id),
                        "status": temporal_result.status.value,
                        "confidence": temporal_result.confidence,
                    },
                )

            if graph_on:
                builder = CrossArtifactEvidenceGraphBuilder(
                    max_nodes=self._settings.evidence_graph_max_nodes,
                    max_edges=self._settings.evidence_graph_max_edges,
                )
                graph = builder.build(
                    analysis_id=str(run.id),
                    organization_id=str(context.organization_id),
                    project_id=str(incident.project_id) if incident.project_id else None,
                    incident_id=str(run.incident_id),
                    artifact_bundle_id=bundle_id_str,
                    bundle=bundle,
                    parse_by_artifact=parse_results,
                    temporal=temporal_result,
                    enabled=True,
                )
                consistency = None
                if consistency_on:
                    consistency = GraphConsistencyEngine().validate(
                        graph,
                        enabled=True,
                        expected_organization_id=str(context.organization_id),
                        expected_project_id=(
                            str(incident.project_id) if incident.project_id else None
                        ),
                    )
                    graph.consistency = consistency
                    if graph.metrics:
                        graph.metrics.consistency_score = consistency.consistency_score
                    if consistency.status.value in {"INVALID", "FAILED"}:
                        await self._record_event(
                            incident_id=run.incident_id,
                            title="Graph validation warning",
                            description=consistency.status.value,
                            event_type="graph_validation_warning",
                            metadata={
                                "analysis_run_id": str(run.id),
                                "status": consistency.status.value,
                                "score": consistency.consistency_score,
                            },
                        )
                await persist.persist_graph(graph, consistency)
                context.options["evidence_graph"] = {
                    "graph_id": graph.id,
                    "status": graph.status.value,
                    "node_count": graph.metrics.node_count,
                    "edge_count": graph.metrics.edge_count,
                    "consistency_status": (
                        consistency.status.value if consistency else None
                    ),
                    "warnings": list(graph.warnings),
                }
                await self._record_event(
                    incident_id=run.incident_id,
                    title="Evidence graph created",
                    description=(
                        f"{graph.metrics.node_count} nodes, "
                        f"{graph.metrics.edge_count} edges"
                    ),
                    event_type="evidence_graph_created",
                    metadata={
                        "analysis_run_id": str(run.id),
                        "graph_id": graph.id,
                        "status": graph.status.value,
                    },
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "phase6a2_pipeline_failed",
                analysis_run_id=str(run.id),
                error=type(exc).__name__,
            )
            context.warnings.append(f"phase6a2_failed:{type(exc).__name__}")
            context.options["phase6a2"] = {"error": type(exc).__name__}
            await self._record_event(
                incident_id=run.incident_id,
                title="Graph construction failed",
                description=type(exc).__name__,
                event_type="graph_construction_failed",
                metadata={"analysis_run_id": str(run.id)},
            )

    async def _maybe_run_phase6a3(
        self,
        run: AnalysisRun,
        context: AnalysisContext,
    ) -> None:
        """Hierarchical classification / open-set / disagreement. Soft-fail additive stage."""
        if not self._settings.hierarchical_classification_enabled:
            return
        if context.organization_id is None:
            return
        try:
            from app.ai.classification.hierarchical_orchestrator import (
                HierarchicalClassificationOrchestrator,
            )
            from app.ai.classification.open_set_detector import (
                OpenSetThresholds,
                parse_category_thresholds_json,
            )
            from app.ai.classification.persist_hierarchical import (
                HierarchicalClassificationPersistService,
            )

            thresholds = OpenSetThresholds(
                confidence_threshold=self._settings.open_set_default_confidence_threshold,
                margin_threshold=self._settings.open_set_default_margin_threshold,
                distance_threshold=self._settings.open_set_default_distance_threshold,
                min_evidence_coverage=self._settings.open_set_min_evidence_coverage,
                category_thresholds=parse_category_thresholds_json(
                    self._settings.open_set_category_thresholds_json
                ),
            )
            orchestrator = HierarchicalClassificationOrchestrator(
                open_set_thresholds=thresholds,
                hierarchical_enabled=True,
                open_set_enabled=bool(self._settings.open_set_detection_enabled),
                disagreement_enabled=bool(self._settings.classification_disagreement_enabled),
                confidence_breakdown_enabled=bool(
                    self._settings.classification_confidence_breakdown_enabled
                ),
                llm_classification_enabled=bool(
                    self._settings.enable_llm and context.enable_llm
                ),
            )
            logger.info(
                "hierarchical_classification_started",
                analysis_run_id=str(run.id),
                organization_id=str(context.organization_id),
                incident_id=str(run.incident_id),
                mapping_version="v1",
            )
            result = orchestrator.run(context)
            persist = HierarchicalClassificationPersistService(self._session)
            await persist.ensure_taxonomy_mappings_seeded()
            await persist.persist(result)
            context.options["hierarchical_classification"] = {
                "status": result.classification_status.value,
                "final_legacy_category_code": result.final_legacy_category_code,
                "level_1_code": result.level_1_code,
                "level_2_code": result.level_2_code,
                "level_3_code": result.level_3_code,
                "final_confidence": result.final_confidence,
                "open_set_status": (
                    result.open_set_result.status.value if result.open_set_result else None
                ),
                "disagreement_level": (
                    result.disagreement_result.agreement_level.value
                    if result.disagreement_result
                    else None
                ),
                "mapping_version": result.mapping_version,
                "duration_ms": result.duration_ms,
                "warnings": list(result.warnings),
            }
            logger.info(
                "hierarchical_classification_completed",
                analysis_run_id=str(run.id),
                organization_id=str(context.organization_id),
                project_id=str(context.options.get("project_id") or ""),
                incident_id=str(run.incident_id),
                status=result.classification_status.value,
                open_set_status=(
                    result.open_set_result.status.value if result.open_set_result else None
                ),
                disagreement_level=(
                    result.disagreement_result.agreement_level.value
                    if result.disagreement_result
                    else None
                ),
                mapping_version=result.mapping_version,
                duration_ms=result.duration_ms,
            )
            await self._record_event(
                incident_id=run.incident_id,
                title="Hierarchical classification completed",
                description=(
                    f"{result.classification_status.value}: "
                    f"{result.level_1_code}/{result.level_2_code}/{result.level_3_code}"
                ),
                event_type="hierarchical_classification_completed",
                metadata={
                    "analysis_run_id": str(run.id),
                    "status": result.classification_status.value,
                    "legacy_category": result.final_legacy_category_code,
                    "open_set_status": (
                        result.open_set_result.status.value if result.open_set_result else None
                    ),
                },
            )
        except Exception as exc:  # noqa: BLE001 - never block legacy classification path
            logger.warning(
                "phase6a3_pipeline_failed",
                analysis_run_id=str(run.id),
                error=type(exc).__name__,
            )
            context.warnings.append(f"phase6a3_failed:{type(exc).__name__}")
            context.options["hierarchical_classification"] = {
                "status": "FAILED",
                "error": type(exc).__name__,
            }
            await self._record_event(
                incident_id=run.incident_id,
                title="Hierarchical classification failed",
                description=type(exc).__name__,
                event_type="hierarchical_classification_failed",
                metadata={"analysis_run_id": str(run.id)},
            )

    async def _maybe_run_phase6a4(
        self,
        run: AnalysisRun,
        context: AnalysisContext,
    ) -> None:
        """Competing causal hypotheses. Soft-fail; does not alter diagnosis/recs."""
        if not self._settings.causal_hypothesis_generation_enabled:
            return
        if context.organization_id is None:
            return
        try:
            from app.ai.hypotheses.orchestrator import CausalHypothesisOrchestrator
            from app.ai.hypotheses.persist import CausalHypothesisPersistService

            llm_complete = None
            if (
                self._settings.llm_hypothesis_generation_enabled
                and self._settings.enable_llm
                and bool(context.options.get("enable_llm", False))
            ):
                # Optional: reuse local structured stub when no external provider path.
                # Full OpenAI wiring can be added later; schema tests cover parse path.
                llm_complete = None

            orchestrator = CausalHypothesisOrchestrator(
                enabled=True,
                rule_enabled=bool(self._settings.rule_hypothesis_generation_enabled),
                llm_enabled=bool(
                    self._settings.llm_hypothesis_generation_enabled
                    and self._settings.enable_llm
                    and bool(context.options.get("enable_llm", False))
                ),
                critic_enabled=bool(self._settings.hypothesis_critic_enabled),
                max_hypotheses=self._settings.max_causal_hypotheses,
                min_hypotheses=self._settings.min_causal_hypotheses,
                graph_max_depth=self._settings.hypothesis_graph_max_depth,
                graph_max_nodes=self._settings.hypothesis_graph_max_nodes,
                graph_max_edges=self._settings.hypothesis_graph_max_edges,
                max_evidence_items=self._settings.hypothesis_max_evidence_items,
                duplicate_similarity_threshold=(
                    self._settings.hypothesis_duplicate_similarity_threshold
                ),
                llm_complete_json=llm_complete,
            )
            logger.info(
                "hypothesis_generation_started",
                analysis_run_id=str(run.id),
                organization_id=str(context.organization_id),
                incident_id=str(run.incident_id),
            )
            # Graph nodes/edges are not always loaded in-memory; pass empty and rely on
            # context.options summaries + evidence/text. Debug APIs can enrich later.
            result = orchestrator.run(context, graph_nodes=[], graph_edges=[])
            await CausalHypothesisPersistService(self._session).persist(result)
            context.options["causal_hypotheses"] = {
                "status": result.status.value,
                "count": len(result.hypotheses),
                "deterministic_count": result.deterministic_count,
                "llm_count": result.llm_count,
                "invalid_reference_count": result.invalid_reference_count,
                "duplicate_removed_count": result.duplicate_removed_count,
                "duration_ms": result.duration_ms,
                "warnings": list(result.warnings),
                "run_id": result.id,
            }
            logger.info(
                "hypothesis_generation_completed",
                analysis_run_id=str(run.id),
                organization_id=str(context.organization_id),
                project_id=str(context.options.get("project_id") or ""),
                incident_id=str(run.incident_id),
                status=result.status.value,
                hypothesis_count=len(result.hypotheses),
                duration_ms=result.duration_ms,
            )
            await self._record_event(
                incident_id=run.incident_id,
                title="Causal hypotheses generated",
                description=f"{result.status.value}: {len(result.hypotheses)} hypotheses",
                event_type="hypothesis_generation_completed",
                metadata={
                    "analysis_run_id": str(run.id),
                    "status": result.status.value,
                    "count": len(result.hypotheses),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "phase6a4_pipeline_failed",
                analysis_run_id=str(run.id),
                error=type(exc).__name__,
            )
            context.warnings.append(f"phase6a4_failed:{type(exc).__name__}")
            context.options["causal_hypotheses"] = {
                "status": "FAILED",
                "error": type(exc).__name__,
            }
            await self._record_event(
                incident_id=run.incident_id,
                title="Causal hypothesis generation failed",
                description=type(exc).__name__,
                event_type="hypothesis_generation_failed",
                metadata={"analysis_run_id": str(run.id)},
            )

    async def _maybe_run_phase6a5_hypothesis_retrieval(
        self,
        run: AnalysisRun,
        context: AnalysisContext,
    ) -> None:
        """Hypothesis-directed retrieval. Soft-fail; does not alter baseline RAG/diagnosis."""
        if not self._settings.hypothesis_directed_rag_enabled:
            return
        if context.organization_id is None:
            return
        try:
            from app.ai.hypothesis_retrieval.orchestrator import (
                HypothesisDirectedRetrievalOrchestrator,
            )

            _, hybrid_pipeline = await build_hybrid_pipeline(self._session, self._settings)
            orchestrator = HypothesisDirectedRetrievalOrchestrator(
                self._settings,
                hybrid_pipeline=hybrid_pipeline,
            )
            logger.info(
                "hypothesis_retrieval_run_started",
                analysis_run_id=str(run.id),
                organization_id=str(context.organization_id),
                incident_id=str(run.incident_id),
                hypothesis_run_id=str(
                    (context.options.get("causal_hypotheses") or {}).get("run_id") or ""
                ),
            )
            result = await orchestrator.run(self._session, context)
            # Never overwrite legacy retrieved_chunks / diagnosis / recommendations.
            context.options["hypothesis_directed_retrieval"] = {
                "status": result.status.value,
                "run_id": result.id,
                "hypothesis_count_processed": result.hypothesis_count_processed,
                "session_count_complete": result.session_count_complete,
                "session_count_partial": result.session_count_partial,
                "session_count_failed": result.session_count_failed,
                "total_query_count": result.total_query_count,
                "total_result_count": result.total_result_count,
                "duration_ms": result.duration_ms,
                "warnings": list(result.warnings),
                "retrieval_pipeline_version": result.retrieval_pipeline_version,
            }
            logger.info(
                "hypothesis_retrieval_run_completed",
                analysis_run_id=str(run.id),
                organization_id=str(context.organization_id),
                project_id=str(context.options.get("project_id") or ""),
                incident_id=str(run.incident_id),
                retrieval_run_id=result.id,
                status=result.status.value,
                hypothesis_count_processed=result.hypothesis_count_processed,
                duration_ms=result.duration_ms,
            )
            await self._record_event(
                incident_id=run.incident_id,
                title="Hypothesis-directed retrieval completed",
                description=(
                    f"{result.status.value}: {result.hypothesis_count_processed} sessions"
                ),
                event_type="hypothesis_retrieval_completed",
                metadata={
                    "analysis_run_id": str(run.id),
                    "status": result.status.value,
                    "processed": result.hypothesis_count_processed,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "phase6a5_hypothesis_retrieval_failed",
                analysis_run_id=str(run.id),
                error=type(exc).__name__,
            )
            context.warnings.append(f"phase6a5_failed:{type(exc).__name__}")
            context.options["hypothesis_directed_retrieval"] = {
                "status": "FAILED",
                "error": type(exc).__name__,
            }
            await self._record_event(
                incident_id=run.incident_id,
                title="Hypothesis-directed retrieval failed",
                description=type(exc).__name__,
                event_type="hypothesis_retrieval_failed",
                metadata={"analysis_run_id": str(run.id)},
            )

    async def _maybe_run_phase6a5_evidence_assessment(
        self,
        run: AnalysisRun,
        context: AnalysisContext,
    ) -> None:
        """Evidence sufficiency / contradiction / ranking / candidates. Soft-fail."""
        if not self._settings.hypothesis_evidence_assessment_enabled:
            return
        if context.organization_id is None:
            return
        try:
            from app.ai.evidence_assessment.orchestrator import EvidenceAssessmentOrchestrator

            orchestrator = EvidenceAssessmentOrchestrator(self._settings)
            logger.info(
                "hypothesis_evidence_assessment_started",
                analysis_run_id=str(run.id),
                organization_id=str(context.organization_id),
            )
            result = await orchestrator.run(self._session, context)
            if result is None:
                return
            # Never overwrite diagnosis / recommendations / retrieved_documents.
            context.options["hypothesis_evidence_assessment"] = result.summary_dict()
            # Richer snapshot for Phase 6A.7 decision inputs only (not a public API contract).
            context.options["hypothesis_evidence_assessment_detail"] = result.to_dict()
            logger.info(
                "hypothesis_evidence_assessment_completed",
                analysis_run_id=str(run.id),
                organization_id=str(context.organization_id),
                status=result.status,
                duration_ms=result.duration_ms,
            )
            await self._record_event(
                incident_id=run.incident_id,
                title="Hypothesis evidence assessment completed",
                description=f"{result.status}: candidates only",
                event_type="hypothesis_evidence_assessment_completed",
                metadata={
                    "analysis_run_id": str(run.id),
                    "status": result.status,
                    "candidate_selection_status": (
                        result.candidate_selection.status.value
                        if result.candidate_selection
                        else None
                    ),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "phase6a5_evidence_assessment_failed",
                analysis_run_id=str(run.id),
                error=type(exc).__name__,
            )
            context.warnings.append(f"phase6a5_evidence_assessment_failed:{type(exc).__name__}")
            context.options["hypothesis_evidence_assessment"] = {
                "status": "FAILED",
                "error": type(exc).__name__,
            }
            await self._record_event(
                incident_id=run.incident_id,
                title="Hypothesis evidence assessment failed",
                description=type(exc).__name__,
                event_type="hypothesis_evidence_assessment_failed",
                metadata={"analysis_run_id": str(run.id)},
            )

    async def _maybe_run_phase6a6_counterfactual_foundation(
        self,
        run: AnalysisRun,
        context: AnalysisContext,
    ) -> None:
        """Counterfactual remediation foundation (Part 1). Soft-fail. No apply/verifiers."""
        if not self._settings.counterfactual_remediation_enabled:
            return
        if context.organization_id is None:
            return
        try:
            from app.ai.counterfactual_remediation.foundation_service import (
                CounterfactualRemediationFoundationService,
            )
            from app.ai.counterfactual_remediation.persist import (
                CounterfactualRemediationPersistService,
            )
            from app.infrastructure.repositories.counterfactual_remediation_repository import (
                CounterfactualRemediationRepositoryImpl,
            )

            persist_service: CounterfactualRemediationPersistService | None = None
            if self._settings.counterfactual_persistence_enabled:
                persist_service = CounterfactualRemediationPersistService(
                    enabled=True,
                    repository=CounterfactualRemediationRepositoryImpl(self._session),
                )

            foundation = CounterfactualRemediationFoundationService(
                self._settings,
                persist_service=persist_service,
            )
            logger.info(
                "counterfactual_remediation_foundation_started",
                analysis_run_id=str(run.id),
                organization_id=str(context.organization_id),
            )
            result = await foundation.run_async(
                organization_id=str(context.organization_id),
                analysis_id=str(run.id),
                options=dict(context.options),
                project_id=str(context.project_id) if context.project_id else None,
                incident_id=str(run.incident_id) if run.incident_id else None,
            )
            # Never overwrite diagnosis / recommendations / retrieved / evidence assessment.
            context.options["counterfactual_remediation"] = result.to_dict()
            # Keep live candidate objects for Part 2 generation (not serialised in to_dict).
            persist_payload = getattr(foundation, "_last_persist_payload", None) or {}
            context.options["_counterfactual_foundation_candidates"] = list(
                persist_payload.get("candidates") or []
            )
            status_value = (
                result.status.value if hasattr(result.status, "value") else str(result.status)
            )
            logger.info(
                "counterfactual_remediation_foundation_completed",
                analysis_run_id=str(run.id),
                organization_id=str(context.organization_id),
                status=status_value,
                duration_ms=result.duration_ms,
                candidate_count=result.candidate_count,
            )
            await self._record_event(
                incident_id=run.incident_id,
                title="Counterfactual remediation foundation completed",
                description=f"{status_value}: candidates only, unverified",
                event_type="counterfactual_remediation_foundation_completed",
                metadata={
                    "analysis_run_id": str(run.id),
                    "status": status_value,
                    "candidate_count": result.candidate_count,
                    "selected_hypothesis_count": result.selected_hypothesis_count,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "phase6a6_counterfactual_foundation_failed",
                analysis_run_id=str(run.id),
                error=type(exc).__name__,
            )
            context.warnings.append(
                f"phase6a6_counterfactual_foundation_failed:{type(exc).__name__}"
            )
            context.options["counterfactual_remediation"] = {
                "status": "FAILED",
                "error": type(exc).__name__,
            }
            await self._record_event(
                incident_id=run.incident_id,
                title="Counterfactual remediation foundation failed",
                description=type(exc).__name__,
                event_type="counterfactual_remediation_foundation_failed",
                metadata={"analysis_run_id": str(run.id)},
            )

    async def _maybe_run_phase6a6_counterfactual_generation(
        self,
        run: AnalysisRun,
        context: AnalysisContext,
    ) -> None:
        """Surface Part 2 generation results (foundation already runs generation).

        Soft-fail. Never overwrites recommendations. Avoids a second generation pass.
        """
        if not (
            self._settings.rule_remediation_generation_enabled
            or self._settings.llm_remediation_generation_enabled
        ):
            context.options.pop("_counterfactual_foundation_candidates", None)
            return
        try:
            foundation_payload = context.options.get("counterfactual_remediation") or {}
            if not isinstance(foundation_payload, dict):
                return
            snapshot = dict(foundation_payload.get("configuration_snapshot") or {})
            gen_meta = dict(snapshot.get("part2_generation_meta") or {})
            prioritisation = gen_meta.get("prioritisation") or snapshot.get("prioritisation")
            if prioritisation and "prioritisation" not in snapshot:
                snapshot["prioritisation"] = prioritisation
                foundation_payload["configuration_snapshot"] = snapshot
                context.options["counterfactual_remediation"] = foundation_payload

            candidates = list(
                context.options.pop("_counterfactual_foundation_candidates", []) or []
            )
            # Keep live objects for Part 3 verifier engine (never serialised into options summary).
            if candidates:
                context.options["_counterfactual_candidates_for_verification"] = candidates
            if self._settings.counterfactual_persistence_enabled and candidates:
                from app.ai.counterfactual_remediation.persist import (
                    CounterfactualRemediationPersistService,
                )
                from app.domain.counterfactual_remediation.enums import (
                    CounterfactualRemediationRunStatus,
                )
                from app.domain.counterfactual_remediation.models import (
                    CounterfactualRemediationRun,
                )
                from app.infrastructure.repositories.counterfactual_remediation_repository import (
                    CounterfactualRemediationRepositoryImpl,
                )

                status_raw = foundation_payload.get("status") or "COMPLETE"
                try:
                    status = CounterfactualRemediationRunStatus(str(status_raw))
                except ValueError:
                    status = CounterfactualRemediationRunStatus.COMPLETE
                rem_run = CounterfactualRemediationRun(
                    id=str(foundation_payload.get("id") or run.id),
                    organization_id=str(context.organization_id or ""),
                    project_id=str(context.project_id or ""),
                    incident_id=str(run.incident_id or ""),
                    analysis_id=str(run.id),
                    status=status,
                    selected_hypothesis_ids=list(
                        foundation_payload.get("selected_hypothesis_ids") or []
                    ),
                    configuration_snapshot=snapshot,
                    warnings=list(foundation_payload.get("warnings") or []),
                    errors=list(foundation_payload.get("errors") or []),
                    limitations=list(foundation_payload.get("limitations") or []),
                    candidate_count=int(
                        foundation_payload.get("candidate_count") or len(candidates)
                    ),
                    safe_candidate_count=int(
                        foundation_payload.get("safe_candidate_count") or 0
                    ),
                    incomplete_candidate_count=int(
                        foundation_payload.get("incomplete_candidate_count") or 0
                    ),
                    rejected_candidate_count=int(
                        foundation_payload.get("rejected_candidate_count") or 0
                    ),
                )
                persist = CounterfactualRemediationPersistService(
                    enabled=True,
                    repository=CounterfactualRemediationRepositoryImpl(self._session),
                )
                await persist.persist_generated_candidates(
                    run=rem_run, candidates=candidates
                )

            context.options["counterfactual_remediation_generation"] = {
                "status": gen_meta.get("status") or ("COMPLETE" if gen_meta else "SKIPPED"),
                "candidate_count": foundation_payload.get("candidate_count"),
                "duration_ms": gen_meta.get("duration_ms"),
                "prioritisation": prioritisation,
                "warnings": list(gen_meta.get("warnings") or []),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "phase6a6_counterfactual_generation_failed",
                analysis_run_id=str(run.id),
                error=type(exc).__name__,
            )
            context.warnings.append(
                f"phase6a6_counterfactual_generation_failed:{type(exc).__name__}"
            )
            context.options["counterfactual_remediation_generation"] = {
                "status": "FAILED",
                "error": type(exc).__name__,
            }

    async def _maybe_run_phase6a6_verifier_engine(
        self,
        run: AnalysisRun,
        context: AnalysisContext,
    ) -> None:
        """Independent verifier engine (Part 3). Soft-fail; never apply."""
        if not self._settings.verifier_engine_enabled:
            context.options.pop("_counterfactual_candidates_for_verification", None)
            return
        if context.organization_id is None:
            return
        try:
            from app.ai.counterfactual_remediation.verification import (
                IndependentVerifierEngine,
                VerificationPersistService,
                build_summary,
            )
            from app.infrastructure.repositories.remediation_verification_repository import (
                RemediationVerificationRepositoryImpl,
            )

            candidates = list(
                context.options.pop("_counterfactual_candidates_for_verification", []) or []
            )
            if (
                not candidates
                and self._settings.counterfactual_persistence_enabled
            ):
                from app.infrastructure.repositories.counterfactual_remediation_repository import (
                    CounterfactualRemediationRepositoryImpl,
                )

                cf_repo = CounterfactualRemediationRepositoryImpl(self._session)
                rows = await cf_repo.list_candidates_by_analysis(
                    organization_id=context.organization_id,
                    analysis_run_id=run.id,
                )
                candidates = list(rows or [])

            persist_service: VerificationPersistService | None = None
            if self._settings.verifier_persistence_enabled:
                persist_service = VerificationPersistService(
                    enabled=True,
                    repository=RemediationVerificationRepositoryImpl(self._session),
                )

            foundation = context.options.get("counterfactual_remediation") or {}
            remediation_run_id = None
            if isinstance(foundation, dict):
                remediation_run_id = foundation.get("id")

            engine = IndependentVerifierEngine(
                self._settings,
                persist_service=persist_service,
            )
            logger.info(
                "counterfactual_verification_started",
                analysis_run_id=str(run.id),
                organization_id=str(context.organization_id),
            )
            report = await engine.run_async(
                organization_id=str(context.organization_id),
                project_id=str(context.project_id) if context.project_id else "",
                incident_id=str(run.incident_id) if run.incident_id else "",
                analysis_id=str(run.id),
                candidates=candidates,
                remediation_run_id=str(remediation_run_id) if remediation_run_id else None,
                options=dict(context.options),
            )
            # Never overwrite diagnosis / recommendations.
            context.options["counterfactual_verification"] = build_summary(report)
            runs_by_candidate = {str(r.candidate_id): r for r in report.runs}
            decision_candidates: list[dict] = []
            for c in candidates:
                cid = str(getattr(c, "id", ""))
                vrun = runs_by_candidate.get(cid)
                results = list(getattr(vrun, "results", None) or []) if vrun else []
                decision_candidates.append(
                    {
                        "candidate_id": cid,
                        "hypothesis_id": str(getattr(c, "hypothesis_id", "") or "") or None,
                        "risk_level": str(getattr(c, "risk_level", "UNKNOWN") or "UNKNOWN"),
                        "risk_score": float(getattr(c, "risk_score", 0.0) or 0.0),
                        "priority_status": str(getattr(c, "priority_status", "") or ""),
                        "priority_score": float(getattr(c, "priority_score", 0.0) or 0.0),
                        "consensus_status": (
                            str(getattr(c, "validation_status", "") or "")
                            or (
                                str(vrun.consensus.status.value)
                                if vrun and vrun.consensus is not None
                                else None
                            )
                        ),
                        "constraint_status": str(getattr(c, "constraint_status", "") or "")
                        or None,
                        "title": str(getattr(c, "title", "") or ""),
                        "summary": str(getattr(c, "summary", "") or ""),
                        "artifact_type": str(getattr(c, "artifact_type", "") or ""),
                        "verifier_results": [
                            {
                                "verifier_name": str(
                                    getattr(r, "verifier_name", None)
                                    or getattr(r, "tool", None)
                                    or ""
                                ),
                                "status": (
                                    r.status.value
                                    if hasattr(getattr(r, "status", None), "value")
                                    else str(getattr(r, "status", "") or "")
                                ),
                            }
                            for r in results
                        ],
                        "required_verifiers": list(
                            getattr(vrun, "selected_verifiers", None) or []
                        ),
                    }
                )
            context.options["_remediation_candidates_for_decision"] = decision_candidates
            status_value = (
                report.status.value
                if hasattr(report.status, "value")
                else str(report.status)
            )
            logger.info(
                "counterfactual_verification_completed",
                analysis_run_id=str(run.id),
                status=status_value,
                run_count=len(report.runs),
            )
            await self._record_event(
                incident_id=run.incident_id,
                title="Counterfactual verification completed",
                description=f"{status_value}: temporary workspace only, not applied",
                event_type="counterfactual_verification_completed",
                metadata={
                    "analysis_run_id": str(run.id),
                    "status": status_value,
                    "verified_count": len(report.candidate_ids_verified),
                    "failed_count": len(report.candidate_ids_failed),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "phase6a6_verifier_engine_failed",
                analysis_run_id=str(run.id),
                error=type(exc).__name__,
            )
            context.warnings.append(f"phase6a6_verifier_engine_failed:{type(exc).__name__}")
            context.options["counterfactual_verification"] = {
                "status": "FAILED",
                "error": type(exc).__name__,
            }
            context.options.pop("_counterfactual_candidates_for_verification", None)

    async def _maybe_run_phase6a7_final_decision(
        self,
        run: AnalysisRun,
        context: AnalysisContext,
    ) -> None:
        """Final diagnosis / confidence / abstention. Soft-fail. Never apply remediation."""
        if not self._settings.final_diagnosis_enabled:
            return
        if context.organization_id is None:
            return
        try:
            from app.ai.final_diagnosis import (
                FinalDiagnosisDecisionEngine,
                build_inputs_from_context,
            )

            inputs = build_inputs_from_context(
                settings=self._settings,
                analysis_id=run.id,
                organization_id=context.organization_id,
                incident_id=run.incident_id,
                project_id=context.options.get("project_id"),
                options=dict(context.options),
            )
            engine = FinalDiagnosisDecisionEngine()
            logger.info(
                "final_diagnosis_started",
                analysis_run_id=str(run.id),
                organization_id=str(context.organization_id),
            )
            decision = engine.decide(inputs)
            payload = decision.to_dict()
            # Never overwrite Module 6 diagnosis / recommendations / incident status.
            context.options["final_diagnosis"] = payload
            status_value = (
                decision.status.value
                if hasattr(decision.status, "value")
                else str(decision.status)
            )
            logger.info(
                "final_diagnosis_completed",
                analysis_run_id=str(run.id),
                status=status_value,
                abstain=bool(decision.abstention and decision.abstention.should_abstain),
            )
            await self._record_event(
                incident_id=run.incident_id,
                title="Final diagnosis decision completed",
                description=(
                    f"{status_value}: evidence-based decision only; "
                    "remediation not applied; not mathematical proof"
                ),
                event_type="final_diagnosis_completed",
                metadata={
                    "analysis_run_id": str(run.id),
                    "status": status_value,
                    "confidence": decision.confidence,
                    "abstention_reasons": list(decision.abstention_reason_codes),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "phase6a7_final_decision_failed",
                analysis_run_id=str(run.id),
                error=type(exc).__name__,
            )
            context.warnings.append(f"phase6a7_final_decision_failed:{type(exc).__name__}")
            context.options["final_diagnosis"] = {
                "status": "FAILED",
                "error": type(exc).__name__,
                "limitations": [
                    "final_diagnosis_is_evidence_based_not_mathematical_proof",
                    "verified_remediation_is_not_applied_remediation",
                ],
            }

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
        organization_id = await self._session.scalar(
            select(Incident.organization_id).where(Incident.id == incident_id)
        )
        if organization_id is None:
            return
        self._session.add(
            IncidentEvent(
                organization_id=organization_id,
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
