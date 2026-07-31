"""Phase 6A.2 temporal localisation unit tests."""

from __future__ import annotations

from app.ai.temporal.localizer import TemporalRootCauseLocalizer
from app.domain.artifacts.enums import ParseStatus
from app.domain.artifacts.models import GraphEntityPreview, StructuredParseResult
from app.domain.temporal.enums import TemporalEventType, TemporalLocalisationStatus


def _log_parse(*labels: tuple[str, str, dict]) -> dict[str, list[StructuredParseResult]]:
    entities = [
        GraphEntityPreview(id=f"e{i}", type=etype, label=label, metadata=meta)
        for i, (etype, label, meta) in enumerate(labels)
    ]
    return {
        "art-1": [
            StructuredParseResult(
                parser_name="log",
                parser_version="1.0.0",
                status=ParseStatus.SUCCESS,
                entities=entities,
                extraction_quality=0.8,
            )
        ]
    }


def test_earliest_meaningful_failure_preferred_over_workflow_failed() -> None:
    parse = _log_parse(
        (
            "ERROR_EVENT",
            "AccessDenied: s3:PutObject",
            {"timestamp": "2026-07-31T10:00:01Z"},
        ),
        (
            "ERROR_EVENT",
            "Process completed with exit code 1",
            {"timestamp": "2026-07-31T10:00:05Z"},
        ),
        ("ERROR_EVENT", "Workflow failed", {"timestamp": "2026-07-31T10:00:06Z"}),
    )
    result = TemporalRootCauseLocalizer().localize(
        analysis_id="a1",
        organization_id="o1",
        parse_by_artifact=parse,
        enabled=True,
    )
    assert result.status in {
        TemporalLocalisationStatus.COMPLETE,
        TemporalLocalisationStatus.PARTIAL,
    }
    assert result.primary_failure_type in {
        TemporalEventType.PERMISSION_DENIED.value,
        TemporalEventType.AUTHENTICATION_FAILURE.value,
    }
    assert result.downstream_symptom_event_ids


def test_generic_downstream_excluded() -> None:
    parse = _log_parse(
        ("ERROR_EVENT", "Error: Reference to undeclared output", {"line_number": 1}),
        ("ERROR_EVENT", "Terraform plan failed", {"line_number": 2}),
        ("ERROR_EVENT", "Job failed", {"line_number": 3}),
    )
    result = TemporalRootCauseLocalizer().localize(
        analysis_id="a1", organization_id="o1", parse_by_artifact=parse, enabled=True
    )
    assert result.primary_failure_type == TemporalEventType.TERRAFORM_DIAGNOSTIC.value


def test_retry_success_suppresses_transient() -> None:
    parse = _log_parse(
        ("ERROR_EVENT", "temporary network error", {"job": "build", "step": "fetch"}),
        ("LOG_EVENT", "Retrying attempt 2", {"job": "build", "step": "fetch"}),
        ("LOG_EVENT", "download succeeded", {"job": "build", "step": "fetch"}),
        ("ERROR_EVENT", "AccessDenied on deploy", {"job": "deploy", "step": "apply"}),
    )
    # Force RETRY classification via message
    parse["art-1"][0].entities[1].label = "Retrying attempt 2"
    result = TemporalRootCauseLocalizer().localize(
        analysis_id="a1", organization_id="o1", parse_by_artifact=parse, enabled=True
    )
    assert result.primary_failure_summary
    assert "AccessDenied" in (result.primary_failure_summary or "")


def test_parallel_jobs_do_not_pick_unrelated_warning() -> None:
    parse = _log_parse(
        (
            "LOG_EVENT",
            "warning: unused import",
            {"job": "test", "timestamp": "2026-07-31T10:00:00Z"},
        ),
        (
            "ERROR_EVENT",
            "AccessDenied deploy",
            {"job": "deploy", "timestamp": "2026-07-31T10:00:10Z"},
        ),
    )
    result = TemporalRootCauseLocalizer().localize(
        analysis_id="a1", organization_id="o1", parse_by_artifact=parse, enabled=True
    )
    assert "AccessDenied" in (result.primary_failure_summary or "")
    assert any(link.link_type.value == "PARALLEL_WITH" for link in result.causal_precedence_links)


def test_missing_timestamps_reduce_confidence() -> None:
    parse = _log_parse(
        ("ERROR_EVENT", "Error: something failed", {}),
        ("ERROR_EVENT", "Process completed with exit code 1", {}),
    )
    result = TemporalRootCauseLocalizer().localize(
        analysis_id="a1", organization_id="o1", parse_by_artifact=parse, enabled=True
    )
    assert "timestamps_absent_using_parser_sequence" in result.warnings
    assert result.confidence < 0.75


def test_disabled_flag() -> None:
    result = TemporalRootCauseLocalizer().localize(
        analysis_id="a1",
        parse_by_artifact={},
        enabled=False,
    )
    assert result.status == TemporalLocalisationStatus.DISABLED
