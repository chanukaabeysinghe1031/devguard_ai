"""Execution / CI log structured parser."""

from __future__ import annotations

import re

from app.ai.artifacts.parsers.base import StructuredArtifactParser
from app.domain.artifacts.enums import ArtifactKind, ParseStatus
from app.domain.artifacts.models import (
    DiagnosticMessage,
    EvidenceCandidate,
    GraphEntityPreview,
    GraphRelationshipPreview,
    SourceLocation,
    StructuredParseResult,
)

PARSER_VERSION = "1.0.0"

_TIMESTAMP_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+"
)
_ERROR_KW_RE = re.compile(r"(?i)\b(error|failed|failure|fatal|exception|panic|traceback)\b")
_WARNING_KW_RE = re.compile(r"(?i)\b(warn(?:ing)?)\b")
_ACCESS_DENIED_RE = re.compile(r"(?i)\bAccessDenied\b|is not authorized to perform")
_TERRAFORM_RE = re.compile(r"(?i)\b(Error:\s|terraform\s+(?:plan|apply|init)|│\s*with\s+)")
_DOCKER_RE = re.compile(
    r"(?i)\b(docker(?:-compose)?|failed to (?:build|pull|push)|denied: requested access)"
)
_STACK_TRACE_RE = re.compile(
    r"(?i)(?:^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\s+)?"
    r"\s*(?:at\s+\S+|File \".+\", line \d+|Traceback \(most recent call last\):)"
)


class LogParser(StructuredArtifactParser):
    name = "log_parser"
    version = PARSER_VERSION

    def supports(self, kind: ArtifactKind) -> bool:
        return kind in {
            ArtifactKind.EXECUTION_LOG,
            ArtifactKind.PREVIOUS_SUCCESS_LOG,
        }

    def parse(
        self,
        content: str,
        *,
        filename: str,
        kind: ArtifactKind,
    ) -> StructuredParseResult:
        entities: list[GraphEntityPreview] = []
        relationships: list[GraphRelationshipPreview] = []
        diagnostics: list[DiagnosticMessage] = []
        evidence: list[EvidenceCandidate] = []
        warnings: list[str] = []
        errors: list[str] = []

        lines = content.splitlines()
        if not lines:
            warnings.append("Empty log content")
            return StructuredParseResult(
                parser_name=self.name,
                parser_version=self.version,
                status=ParseStatus.PARTIAL,
                warnings=warnings,
                extraction_quality=0.1,
                raw_summary={"filename": filename, "line_count": 0},
            )

        timestamped = 0
        error_line_indexes: list[int] = []
        warning_count = 0
        access_denied_count = 0
        terraform_hits = 0
        docker_hits = 0
        stack_trace_count = 0
        first_error: dict[str, object] | None = None

        for idx, line in enumerate(lines, start=1):
            ts_match = _TIMESTAMP_RE.match(line)
            timestamp = ts_match.group("ts") if ts_match else None
            if timestamp:
                timestamped += 1

            is_error = bool(_ERROR_KW_RE.search(line)) or bool(_ACCESS_DENIED_RE.search(line))
            is_warning = bool(_WARNING_KW_RE.search(line))
            is_access_denied = bool(_ACCESS_DENIED_RE.search(line))
            is_terraform = bool(_TERRAFORM_RE.search(line))
            is_docker = bool(_DOCKER_RE.search(line))
            is_stack = bool(_STACK_TRACE_RE.search(line))

            if is_warning:
                warning_count += 1
            if is_access_denied:
                access_denied_count += 1
            if is_terraform:
                terraform_hits += 1
            if is_docker:
                docker_hits += 1
            if is_stack:
                stack_trace_count += 1

            patterns: list[str] = []
            if is_access_denied:
                patterns.append("AccessDenied")
            if is_terraform:
                patterns.append("terraform")
            if is_docker:
                patterns.append("docker")
            if is_stack:
                patterns.append("stack_trace")

            if is_error or is_access_denied or is_stack:
                error_line_indexes.append(idx)
                entity_id = f"error:{idx}"
                entities.append(
                    GraphEntityPreview(
                        id=entity_id,
                        type="ERROR_EVENT",
                        label=line.strip()[:160],
                        location=SourceLocation(
                            path=filename,
                            line_start=idx,
                            line_end=idx,
                        ),
                        metadata={
                            "timestamp": timestamp,
                            "patterns": patterns,
                            "line_number": idx,
                        },
                    )
                )
                importance = 0.9 if is_access_denied else 0.75
                evidence.append(
                    EvidenceCandidate(
                        kind="log_error",
                        text=line.strip()[:1000],
                        location=SourceLocation(
                            path=filename,
                            line_start=idx,
                            line_end=idx,
                        ),
                        importance=importance,
                        metadata={"patterns": patterns, "timestamp": timestamp},
                    )
                )
                if first_error is None:
                    first_error = {
                        "line_number": idx,
                        "text": line.strip()[:500],
                        "timestamp": timestamp,
                        "patterns": patterns,
                    }
            elif timestamp or is_warning or is_terraform or is_docker:
                entity_id = f"log:{idx}"
                entities.append(
                    GraphEntityPreview(
                        id=entity_id,
                        type="LOG_EVENT",
                        label=line.strip()[:160],
                        location=SourceLocation(
                            path=filename,
                            line_start=idx,
                            line_end=idx,
                        ),
                        metadata={
                            "timestamp": timestamp,
                            "patterns": patterns,
                            "is_warning": is_warning,
                            "line_number": idx,
                        },
                    )
                )

        # OCCURRED_BEFORE between consecutive error events
        for left, right in zip(error_line_indexes, error_line_indexes[1:], strict=False):
            relationships.append(
                GraphRelationshipPreview(
                    source_id=f"error:{left}",
                    target_id=f"error:{right}",
                    type="OCCURRED_BEFORE",
                    confidence=1.0,
                    explanation=f"Error at line {left} precedes error at line {right}",
                    deterministic=True,
                )
            )

        if access_denied_count:
            diagnostics.append(
                DiagnosticMessage(
                    severity="error",
                    code="access_denied_detected",
                    message=f"Detected {access_denied_count} AccessDenied-related line(s)",
                )
            )

        status = ParseStatus.SUCCESS
        if not entities:
            status = ParseStatus.PARTIAL
            warnings.append("No structured log events extracted")

        quality = min(
            1.0,
            0.2
            + (0.3 if timestamped else 0.0)
            + (0.3 if error_line_indexes else 0.1)
            + (0.2 if access_denied_count or terraform_hits or docker_hits else 0.0),
        )

        return StructuredParseResult(
            parser_name=self.name,
            parser_version=self.version,
            status=status,
            entities=entities,
            relationships=relationships,
            diagnostics=diagnostics,
            evidence_candidates=evidence,
            warnings=warnings,
            errors=errors,
            extraction_quality=quality,
            raw_summary={
                "filename": filename,
                "kind": kind.value,
                "line_count": len(lines),
                "timestamped_lines": timestamped,
                "error_event_count": len(error_line_indexes),
                "warning_keyword_lines": warning_count,
                "access_denied_count": access_denied_count,
                "terraform_pattern_hits": terraform_hits,
                "docker_pattern_hits": docker_hits,
                "stack_trace_lines": stack_trace_count,
                "first_error": first_error,
            },
        )
