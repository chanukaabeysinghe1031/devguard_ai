"""Hybrid diagnostic query builder — masked, bounded, structured."""

from __future__ import annotations

import re
from uuid import UUID

from app.ai.orchestration.analysis_context import AnalysisContext
from app.ai.rag.models import DiagnosticQuery
from app.ai.rag.signals import DiagnosticSignalExtractor, DiagnosticSignals
from app.domain.services.secret_masker import mask_secrets

_TIMESTAMP = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b")
_MAX_QUERY_LEN = 800


class HybridDiagnosticQueryBuilder:
    def __init__(self, signal_extractor: DiagnosticSignalExtractor | None = None) -> None:
        self._signals = signal_extractor or DiagnosticSignalExtractor()

    def build(self, context: AnalysisContext) -> DiagnosticQuery:
        signals = self._signals.extract(context)
        # Phase 6A.5: optional explicit query override for hypothesis-directed adapters.
        override = context.options.get("hypothesis_directed_query")
        if isinstance(override, str) and override.strip():
            raw_text = override.strip()
            sanitised = self._sanitise(raw_text)
        else:
            raw_parts = self._semantic_parts(context, signals)
            raw_text = " ".join(raw_parts)
            sanitised = self._sanitise(raw_text)

        org_id = context.organization_id
        if org_id is None and context.options.get("organisation_id"):
            try:
                org_id = UUID(str(context.options["organisation_id"]))
            except (TypeError, ValueError):
                org_id = None
        project_id = None
        if context.options.get("project_id"):
            try:
                project_id = UUID(str(context.options["project_id"]))
            except (TypeError, ValueError):
                project_id = None

        query = DiagnosticQuery(
            raw_text=raw_text[:_MAX_QUERY_LEN],
            sanitised_text=sanitised,
            failure_category=signals.failure_category,
            pipeline_stage=signals.pipeline_stage,
            technologies=list(signals.technologies),
            error_codes=list(signals.error_codes),
            exception_names=list(signals.exception_names),
            commands=list(signals.commands),
            resource_types=list(signals.resource_types),
            file_types=list(signals.file_types),
            aws_services=list(signals.aws_services),
            keywords=list(signals.keywords),
            stack_trace_fingerprint=signals.stack_trace_fingerprint,
            organisation_id=org_id,
            project_id=project_id,
            incident_id=context.incident_id,
        )

        # Phase 6A.5 Part 2: hypothesis-scoped structured DiagnosticQuery fields.
        # When present with a directed override, do not rely on rank-1 classifications.
        structured = context.options.get("hypothesis_directed_structured")
        if (
            isinstance(override, str)
            and override.strip()
            and isinstance(structured, dict)
        ):
            if structured.get("failure_category"):
                query.failure_category = str(structured["failure_category"])
            if isinstance(structured.get("error_codes"), list):
                query.error_codes = [str(x) for x in structured["error_codes"] if x][:12]
            if isinstance(structured.get("exception_names"), list):
                query.exception_names = [
                    str(x) for x in structured["exception_names"] if x
                ][:8]
            if isinstance(structured.get("keywords"), list):
                query.keywords = [str(x) for x in structured["keywords"] if x][:20]
            if isinstance(structured.get("aws_services"), list):
                query.aws_services = [str(x) for x in structured["aws_services"] if x][:8]
            if isinstance(structured.get("resource_types"), list):
                query.resource_types = [
                    str(x) for x in structured["resource_types"] if x
                ][:8]
            if isinstance(structured.get("technologies"), list):
                query.technologies = [str(x) for x in structured["technologies"] if x][:8]
            if structured.get("pipeline_stage"):
                query.pipeline_stage = str(structured["pipeline_stage"])

        context.retrieval_query = query.sanitised_text
        context.options["diagnostic_query_summary"] = query.signal_summary()
        return query

    def _semantic_parts(
        self,
        context: AnalysisContext,
        signals: DiagnosticSignals,
    ) -> list[str]:
        parts: list[str] = []
        if signals.failure_category:
            parts.append(signals.failure_category.replace("_", " "))
        if context.classifications:
            parts.append(context.classifications[0].root_cause_summary)
        parts.extend(signals.error_codes[:6])
        parts.extend(signals.exception_names[:4])
        parts.extend(signals.commands[:4])
        if signals.pipeline_stage:
            parts.append(signals.pipeline_stage)
        parts.extend(signals.technologies[:6])
        parts.extend(signals.aws_services[:4])
        parts.extend(signals.resource_types[:4])
        for item in context.evidence[:4]:
            parts.append((item.normalized_excerpt or "")[:180])
        return [p.strip() for p in parts if p and str(p).strip()]

    def _sanitise(self, text: str) -> str:
        masked, _ = mask_secrets(text or "")
        # Remove noisy timestamps; keep error content.
        cleaned = _TIMESTAMP.sub(" ", masked)
        # Collapse repeated consecutive lines.
        lines: list[str] = []
        prev = None
        for line in cleaned.splitlines() or [cleaned]:
            normalised = " ".join(line.split())
            if not normalised or normalised == prev:
                continue
            lines.append(normalised)
            prev = normalised
        joined = " ".join(lines)
        return joined[:_MAX_QUERY_LEN]
