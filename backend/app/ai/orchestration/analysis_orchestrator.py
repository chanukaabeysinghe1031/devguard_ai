"""Central analysis orchestrator — explicit staged pipeline (no AI provider required)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from uuid import UUID

import structlog

from app.ai.classification.hybrid_classifier import HybridClassifier
from app.ai.evidence.evidence_extractor import EvidenceExtractor
from app.ai.guardrails.output_guardrails import OutputGuardrails
from app.ai.orchestration.analysis_context import AnalysisContext, LoadedFile, StageResult
from app.ai.recommendations.recommendation_generator import RecommendationGenerator
from app.domain.enums import AnalysisRunStatus, FileType
from app.domain.services.file_validation import decode_text_content
from app.domain.services.secret_masker import mask_secrets

logger = structlog.get_logger(__name__)

ProgressCallback = Callable[[AnalysisRunStatus, str, int, list[StageResult]], Any]


class AnalysisOrchestrator:
    """Runs the deterministic analysis pipeline for one analysis_run."""

    def __init__(
        self,
        *,
        classifier: HybridClassifier | None = None,
        evidence_extractor: EvidenceExtractor | None = None,
        recommendation_generator: RecommendationGenerator | None = None,
        guardrails: OutputGuardrails | None = None,
    ) -> None:
        self._classifier = classifier or HybridClassifier()
        self._evidence = evidence_extractor or EvidenceExtractor()
        self._recommendations = recommendation_generator or RecommendationGenerator()
        self._guardrails = guardrails or OutputGuardrails()

    async def run(
        self,
        context: AnalysisContext,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> AnalysisContext:
        async def _stage(
            name: str,
            status: AnalysisRunStatus,
            progress: int,
            fn: Callable[[], None],
            *,
            skip: bool = False,
            skip_reason: str | None = None,
        ) -> None:
            started = time.perf_counter()
            if skip:
                context.stages.append(
                    StageResult(
                        name=name,
                        status="skipped",
                        duration_ms=0,
                        detail=skip_reason,
                    )
                )
                context.partial = True
                if on_progress:
                    await _maybe_await(on_progress(status, name, progress, context.stages))
                return
            try:
                fn()
                duration = int((time.perf_counter() - started) * 1000)
                context.stages.append(
                    StageResult(name=name, status="completed", duration_ms=duration)
                )
                if on_progress:
                    await _maybe_await(on_progress(status, name, progress, context.stages))
            except Exception as exc:
                duration = int((time.perf_counter() - started) * 1000)
                context.stages.append(
                    StageResult(
                        name=name,
                        status="failed",
                        duration_ms=duration,
                        detail=str(exc)[:500],
                    )
                )
                raise

        await _stage(
            "validating",
            AnalysisRunStatus.PREPROCESSING,
            5,
            lambda: self._validate(context),
        )
        await _stage(
            "masking_secrets",
            AnalysisRunStatus.PREPROCESSING,
            12,
            lambda: self._mask(context),
        )
        await _stage(
            "parsing",
            AnalysisRunStatus.PREPROCESSING,
            18,
            lambda: self._detect_input_type(context),
        )
        await _stage(
            "preprocessing",
            AnalysisRunStatus.PREPROCESSING,
            25,
            lambda: self._normalize(context),
        )
        await _stage(
            "extracting_signals",
            AnalysisRunStatus.CLASSIFYING,
            35,
            lambda: self._extract_signals(context),
        )
        await _stage(
            "classifying",
            AnalysisRunStatus.CLASSIFYING,
            50,
            lambda: self._classifier.classify(context),
        )
        await _stage(
            "extracting_evidence",
            AnalysisRunStatus.CLASSIFYING,
            60,
            lambda: self._evidence.extract(context),
        )
        await _stage(
            "retrieving_knowledge",
            AnalysisRunStatus.RETRIEVING,
            70,
            lambda: None,
            skip=not context.enable_rag,
            skip_reason="RAG disabled for deterministic MVP execution.",
        )
        await _stage(
            "reasoning",
            AnalysisRunStatus.REASONING,
            78,
            lambda: None,
            skip=not context.enable_llm,
            skip_reason="LLM disabled; using classifier root-cause summaries.",
        )
        await _stage(
            "generating_recommendations",
            AnalysisRunStatus.REASONING,
            88,
            lambda: self._recommendations.generate(context),
            skip=not context.generate_recommendations,
            skip_reason="Recommendation generation disabled by options.",
        )
        await _stage(
            "validating_output",
            AnalysisRunStatus.REASONING,
            94,
            lambda: self._guardrails.validate(context),
        )
        if on_progress:
            await _maybe_await(
                on_progress(
                    AnalysisRunStatus.REASONING,
                    "persisting",
                    97,
                    context.stages,
                )
            )
        return context

    def _validate(self, context: AnalysisContext) -> None:
        if not context.files:
            raise ValueError("No approved files available for analysis.")
        for loaded in context.files:
            if not loaded.content.strip():
                raise ValueError(f"File '{loaded.original_filename}' is empty after load.")

    def _mask(self, context: AnalysisContext) -> None:
        for loaded in context.files:
            masked, count = mask_secrets(loaded.content)
            loaded.content = masked
            if count:
                context.warnings.append(
                    f"Re-masked {count} secret pattern(s) in {loaded.original_filename}."
                )

    def _detect_input_type(self, context: AnalysisContext) -> None:
        types = {f.file_type for f in context.files}
        if len(types) == 1:
            context.input_type = next(iter(types)).value
        else:
            context.input_type = "mixed"

    def _normalize(self, context: AnalysisContext) -> None:
        parts: list[str] = []
        for loaded in context.files:
            normalized = loaded.content.replace("\r\n", "\n").replace("\r", "\n")
            # Collapse excessive blank lines.
            lines = [line.rstrip() for line in normalized.split("\n")]
            cleaned: list[str] = []
            blank = 0
            for line in lines:
                if line.strip() == "":
                    blank += 1
                    if blank <= 2:
                        cleaned.append("")
                else:
                    blank = 0
                    cleaned.append(line)
            loaded.content = "\n".join(cleaned)
            parts.append(
                f"===== FILE: {loaded.original_filename} ({loaded.file_type.value}) =====\n"
                f"{loaded.content}"
            )
        context.combined_text = "\n\n".join(parts)

    def _extract_signals(self, context: AnalysisContext) -> None:
        text = context.combined_text
        context.signals = {
            "line_count": text.count("\n") + 1 if text else 0,
            "char_count": len(text),
            "file_count": len(context.files),
            "input_type": context.input_type,
            "has_error_keyword": "error" in text.lower() or "failed" in text.lower(),
            "file_types": sorted({f.file_type.value for f in context.files}),
        }


async def _maybe_await(result: Any) -> Any:
    if hasattr(result, "__await__"):
        return await result
    return result


def build_loaded_file(
    *,
    file_id: UUID,
    original_filename: str,
    file_type: FileType,
    raw_bytes: bytes,
    storage_path: str,
) -> LoadedFile:
    """Decode storage bytes into a LoadedFile (expects text already largely masked)."""
    text = decode_text_content(raw_bytes)
    return LoadedFile(
        file_id=file_id,
        original_filename=original_filename,
        file_type=file_type,
        content=text,
        storage_path=storage_path,
    )
