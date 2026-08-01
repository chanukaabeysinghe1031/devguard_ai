# ruff: noqa: E501
"""Normalize StructuredParseResult entities into TemporalEvent sequences."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from app.domain.artifacts.models import GraphEntityPreview, SourceLocation, StructuredParseResult
from app.domain.temporal.enums import TemporalEventType
from app.domain.temporal.models import TemporalEvent

_TS_RE = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"
)
_EXIT_RE = re.compile(r"exit(?:ed)?(?:\s+with)?(?:\s+code)?\s*[:=]?\s*(\d+)", re.I)
_GENERIC_DOWNSTREAM = re.compile(
    r"(process completed with exit code|job failed|workflow failed|##\[error\]Process completed)",
    re.I,
)
_AUTH = re.compile(r"(accessdenied|not authorized|unauthorized|authentication failed)", re.I)
_PERM = re.compile(r"(permission|AccessDenied|explicit deny|not permitted)", re.I)
_TF_DIAG = re.compile(
    r"(Error:|Warning:|terraform|Invalid reference|Reference to undeclared)", re.I
)
_DEP = re.compile(r"(could not resolve|ENOENT|module not found|package not found)", re.I)
_TIMEOUT = re.compile(r"(timed? out|timeout exceeded)", re.I)
_RETRY = re.compile(r"(retrying|retry\s+\d|attempt\s+\d+)", re.I)
_CANCEL = re.compile(r"(cancelled|canceled|Canceling)", re.I)
_TEST = re.compile(r"(test failed|assertion|FAILED\s+\S+)", re.I)
_RESOURCE = re.compile(r"(resource .+ not found|NoSuchBucket|does not exist)", re.I)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _classify_message(message: str, entity_type: str) -> TemporalEventType:
    text = message or ""
    if _CANCEL.search(text):
        return TemporalEventType.CANCELLATION
    if _RETRY.search(text):
        return TemporalEventType.RETRY
    if _TIMEOUT.search(text):
        return TemporalEventType.TIMEOUT
    if _AUTH.search(text) and _PERM.search(text):
        return TemporalEventType.PERMISSION_DENIED
    if _AUTH.search(text):
        return TemporalEventType.AUTHENTICATION_FAILURE
    if _PERM.search(text):
        return TemporalEventType.PERMISSION_DENIED
    if _TF_DIAG.search(text) and ("Error" in text or "error" in text.lower()):
        return TemporalEventType.TERRAFORM_DIAGNOSTIC
    if _DEP.search(text):
        return TemporalEventType.DEPENDENCY_FAILURE
    if _TEST.search(text):
        return TemporalEventType.TEST_FAILURE
    if _RESOURCE.search(text):
        return TemporalEventType.RESOURCE_FAILURE
    if _GENERIC_DOWNSTREAM.search(text):
        if "workflow" in text.lower():
            return TemporalEventType.WORKFLOW_FAILED
        if "job" in text.lower():
            return TemporalEventType.JOB_FAILED
        return TemporalEventType.ERROR
    if entity_type == "ERROR_EVENT" or "error" in text.lower() or "failed" in text.lower():
        return TemporalEventType.ERROR
    if "warning" in text.lower():
        return TemporalEventType.WARNING
    return TemporalEventType.INFO


def _severity_for(event_type: TemporalEventType) -> str:
    if event_type in {
        TemporalEventType.AUTHENTICATION_FAILURE,
        TemporalEventType.PERMISSION_DENIED,
        TemporalEventType.TERRAFORM_DIAGNOSTIC,
        TemporalEventType.DEPENDENCY_FAILURE,
        TemporalEventType.RESOURCE_FAILURE,
        TemporalEventType.TEST_FAILURE,
        TemporalEventType.ERROR,
        TemporalEventType.JOB_FAILED,
        TemporalEventType.WORKFLOW_FAILED,
        TemporalEventType.TIMEOUT,
    }:
        return "error"
    if event_type in {TemporalEventType.WARNING, TemporalEventType.RETRY}:
        return "warning"
    return "info"


def normalize_parse_results_to_events(
    *,
    analysis_id: str,
    organization_id: str | None,
    project_id: str | None,
    parse_by_artifact: dict[str, list[StructuredParseResult]],
    workflow_name: str | None = None,
    max_events: int = 5000,
) -> tuple[list[TemporalEvent], list[str]]:
    """Convert parser entities into ordered TemporalEvent list (parser sequence)."""
    events: list[TemporalEvent] = []
    warnings: list[str] = []
    seq = 0
    truncated = False

    for artifact_id, results in sorted(parse_by_artifact.items()):
        for parsed in results:
            for entity in parsed.entities:
                if seq >= max_events:
                    truncated = True
                    break
                event = _entity_to_event(
                    entity,
                    analysis_id=analysis_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    artifact_id=artifact_id,
                    sequence_index=seq,
                    workflow_name=workflow_name,
                    extraction_quality=parsed.extraction_quality,
                )
                if event is None:
                    continue
                events.append(event)
                seq += 1
            if truncated:
                break
        if truncated:
            break

    if truncated:
        warnings.append(f"temporal_events_truncated_at_{max_events}")
    return events, warnings


def _entity_to_event(
    entity: GraphEntityPreview,
    *,
    analysis_id: str,
    organization_id: str | None,
    project_id: str | None,
    artifact_id: str,
    sequence_index: int,
    workflow_name: str | None,
    extraction_quality: float | None,
) -> TemporalEvent | None:
    etype = entity.type.upper()
    meta = dict(entity.metadata or {})
    message = entity.label
    if etype in {"ERROR_EVENT", "LOG_EVENT", "AWS_ERROR"}:
        pass
    elif etype == "JOB":
        return TemporalEvent(
            id=str(uuid.uuid4()),
            analysis_id=analysis_id,
            organization_id=organization_id,
            project_id=project_id,
            artifact_id=artifact_id,
            event_type=TemporalEventType.JOB_STARTED,
            sequence_index=sequence_index,
            workflow_name=workflow_name,
            job_name=entity.label,
            message=f"Job {entity.label}",
            severity="info",
            source_location=entity.location,
            parser_entity_id=entity.id,
            metadata=meta,
            extraction_confidence=extraction_quality or 0.7,
        )
    elif etype == "STEP":
        return TemporalEvent(
            id=str(uuid.uuid4()),
            analysis_id=analysis_id,
            organization_id=organization_id,
            project_id=project_id,
            artifact_id=artifact_id,
            event_type=TemporalEventType.STEP_STARTED,
            sequence_index=sequence_index,
            workflow_name=workflow_name,
            job_name=str(meta.get("job") or meta.get("job_key") or ""),
            step_name=entity.label,
            message=f"Step {entity.label}",
            severity="info",
            source_location=entity.location,
            parser_entity_id=entity.id,
            metadata=meta,
            extraction_confidence=extraction_quality or 0.7,
        )
    elif etype == "COMMAND":
        return TemporalEvent(
            id=str(uuid.uuid4()),
            analysis_id=analysis_id,
            organization_id=organization_id,
            project_id=project_id,
            artifact_id=artifact_id,
            event_type=TemporalEventType.COMMAND_EXECUTED,
            sequence_index=sequence_index,
            workflow_name=workflow_name,
            job_name=str(meta.get("job") or ""),
            step_name=str(meta.get("step") or ""),
            command=str(meta.get("run") or entity.label),
            message=entity.label,
            severity="info",
            source_location=entity.location,
            parser_entity_id=entity.id,
            metadata=meta,
            extraction_confidence=extraction_quality or 0.7,
        )
    elif etype not in {"ERROR_EVENT", "LOG_EVENT", "AWS_ERROR"}:
        return None

    ts_raw = meta.get("timestamp")
    if isinstance(ts_raw, str):
        timestamp = _parse_ts(ts_raw)
    else:
        m = _TS_RE.search(message)
        timestamp = _parse_ts(m.group("ts") if m else None)

    event_type = _classify_message(message, etype)
    exit_m = _EXIT_RE.search(message)
    exit_code = int(exit_m.group(1)) if exit_m else None
    is_failure = (
        event_type
        not in {
            TemporalEventType.INFO,
            TemporalEventType.WARNING,
            TemporalEventType.JOB_STARTED,
            TemporalEventType.STEP_STARTED,
            TemporalEventType.COMMAND_EXECUTED,
            TemporalEventType.WORKFLOW_STARTED,
            TemporalEventType.RETRY,
        }
        or etype == "ERROR_EVENT"
    )

    return TemporalEvent(
        id=str(uuid.uuid4()),
        analysis_id=analysis_id,
        organization_id=organization_id,
        project_id=project_id,
        artifact_id=artifact_id,
        event_type=event_type,
        sequence_index=sequence_index,
        timestamp=timestamp,
        workflow_name=workflow_name,
        job_name=str(meta.get("job") or meta.get("job_key") or "") or None,
        step_name=str(meta.get("step") or meta.get("step_name") or "") or None,
        command=str(meta.get("run") or "") or None,
        exit_code=exit_code,
        message=message[:2000],
        severity=_severity_for(event_type),
        source_location=entity.location
        or SourceLocation(path=None, line_start=meta.get("line_number")),
        parser_entity_id=entity.id,
        is_failure=is_failure,
        metadata={**meta, "patterns": meta.get("patterns")},
        extraction_confidence=float(extraction_quality or 0.6),
    )


def is_generic_downstream(event: TemporalEvent) -> bool:
    """True for status/exit wrappers that usually are symptoms, not root causes."""
    if event.event_type in {
        TemporalEventType.WORKFLOW_FAILED,
        TemporalEventType.JOB_FAILED,
    }:
        return True
    msg = event.message or ""
    if _GENERIC_DOWNSTREAM.search(msg):
        return True
    return (
        event.exit_code is not None
        and event.event_type == TemporalEventType.ERROR
        and not any(
            p.search(msg) for p in (_AUTH, _PERM, _TF_DIAG, _DEP, _RESOURCE, _TEST, _TIMEOUT)
        )
    )


def causal_priority(event: TemporalEvent) -> int:
    """Higher = more likely initiating failure."""
    ranking = {
        TemporalEventType.AUTHENTICATION_FAILURE: 100,
        TemporalEventType.PERMISSION_DENIED: 95,
        TemporalEventType.TERRAFORM_DIAGNOSTIC: 90,
        TemporalEventType.DEPENDENCY_FAILURE: 85,
        TemporalEventType.RESOURCE_FAILURE: 80,
        TemporalEventType.TEST_FAILURE: 70,
        TemporalEventType.TIMEOUT: 60,
        TemporalEventType.ERROR: 50,
        TemporalEventType.JOB_FAILED: 20,
        TemporalEventType.WORKFLOW_FAILED: 10,
    }
    return ranking.get(event.event_type, 0)
