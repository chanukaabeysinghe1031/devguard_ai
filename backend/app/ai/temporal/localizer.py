# ruff: noqa: E501
"""Deterministic temporal root-cause localisation (Phase 6A.2)."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from datetime import datetime

import structlog

from app.ai.temporal.event_normalizer import (
    causal_priority,
    is_generic_downstream,
    normalize_parse_results_to_events,
)
from app.domain.artifacts.models import StructuredParseResult
from app.domain.temporal.enums import (
    TemporalEventType,
    TemporalLinkDerivation,
    TemporalLinkType,
    TemporalLocalisationStatus,
    TemporalOrderingMethod,
    TimestampQuality,
)
from app.domain.temporal.models import (
    HEURISTIC_VERSION,
    TemporalCausalLink,
    TemporalEvent,
    TemporalLocalisationResult,
)

logger = structlog.get_logger(__name__)

RULE_PRIMARY = "TL-PRIMARY-EARLIEST-v1"
RULE_SYMPTOM = "TL-DOWNSTREAM-SYMPTOM-v1"
RULE_RETRY_SKIP = "TL-RETRY-SUCCESS-v1"
RULE_RETRY_KEEP = "TL-RETRY-FAIL-v1"
RULE_PARALLEL = "TL-PARALLEL-PARTIAL-v1"
RULE_ORDER = "TL-ORDER-v1"


class TemporalRootCauseLocalizer:
    """Identify earliest meaningful failure and mark downstream symptoms."""

    def __init__(self, *, max_events: int = 5000) -> None:
        self._max_events = max_events

    def localize(
        self,
        *,
        analysis_id: str,
        organization_id: str | None = None,
        project_id: str | None = None,
        artifact_bundle_id: str | None = None,
        parse_by_artifact: dict[str, list[StructuredParseResult]],
        workflow_name: str | None = None,
        enabled: bool = True,
    ) -> TemporalLocalisationResult:
        started = time.perf_counter()
        if not enabled:
            return TemporalLocalisationResult(
                analysis_id=analysis_id,
                status=TemporalLocalisationStatus.DISABLED,
                organization_id=organization_id,
                project_id=project_id,
                artifact_bundle_id=artifact_bundle_id,
            )

        logger.info(
            "temporal_localisation_started",
            analysis_id=analysis_id,
            organization_id=organization_id,
            artifact_bundle_id=artifact_bundle_id,
        )
        try:
            events, warnings = normalize_parse_results_to_events(
                analysis_id=analysis_id,
                organization_id=organization_id,
                project_id=project_id,
                parse_by_artifact=parse_by_artifact,
                workflow_name=workflow_name,
                max_events=self._max_events,
            )
            if not events:
                return TemporalLocalisationResult(
                    analysis_id=analysis_id,
                    status=TemporalLocalisationStatus.INCONCLUSIVE,
                    warnings=warnings + ["no_temporal_events"],
                    missing_information=["execution_events"],
                    organization_id=organization_id,
                    project_id=project_id,
                    artifact_bundle_id=artifact_bundle_id,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )

            ordered, ordering_method, ts_quality, order_warnings = self._order_events(events)
            warnings.extend(order_warnings)
            links = self._build_order_links(ordered, ordering_method)
            links.extend(self._build_parallel_links(ordered))
            links.extend(self._build_structure_links(ordered))

            failures = [e for e in ordered if e.is_failure]
            if not failures:
                result = TemporalLocalisationResult(
                    analysis_id=analysis_id,
                    status=TemporalLocalisationStatus.INCONCLUSIVE,
                    events=ordered,
                    causal_precedence_links=links,
                    ordering_method=ordering_method,
                    timestamp_quality=ts_quality,
                    confidence=0.2,
                    warnings=warnings + ["no_failure_events"],
                    missing_information=["failure_events"],
                    organization_id=organization_id,
                    project_id=project_id,
                    artifact_bundle_id=artifact_bundle_id,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
                return result

            primary, symptom_ids, retry_warnings = self._select_primary(ordered, failures)
            warnings.extend(retry_warnings)
            for event in ordered:
                event.is_candidate_primary_failure = event.id == primary.id

            for symptom_id in symptom_ids:
                links.append(
                    TemporalCausalLink(
                        id=str(uuid.uuid4()),
                        source_event_id=symptom_id,
                        target_event_id=primary.id,
                        link_type=TemporalLinkType.DOWNSTREAM_SYMPTOM_OF,
                        derivation=TemporalLinkDerivation.TEMPORAL_HEURISTIC,
                        confidence=0.7,
                        explanation=(
                            "Later generic failure treated as downstream symptom of "
                            "earlier higher-priority error (not proven causality)."
                        ),
                        supporting_event_ids=[primary.id, symptom_id],
                        rule_id=RULE_SYMPTOM,
                        rule_version=HEURISTIC_VERSION,
                        proven_causality=False,
                    )
                )
                links.append(
                    TemporalCausalLink(
                        id=str(uuid.uuid4()),
                        source_event_id=primary.id,
                        target_event_id=symptom_id,
                        link_type=TemporalLinkType.CANDIDATE_CAUSE_OF,
                        derivation=TemporalLinkDerivation.TEMPORAL_HEURISTIC,
                        confidence=0.65,
                        explanation=(
                            "Heuristic candidate cause — not confirmed causality."
                        ),
                        supporting_event_ids=[primary.id, symptom_id],
                        rule_id=RULE_PRIMARY,
                        rule_version=HEURISTIC_VERSION,
                        proven_causality=False,
                    )
                )

            upstream = [
                e.id
                for e in ordered
                if e.sequence_index < primary.sequence_index
                and e.event_type
                in {
                    TemporalEventType.JOB_STARTED,
                    TemporalEventType.STEP_STARTED,
                    TemporalEventType.COMMAND_EXECUTED,
                    TemporalEventType.RETRY,
                }
            ][-10:]

            confidence = self._confidence(
                primary=primary,
                failures=failures,
                ts_quality=ts_quality,
                ordering_method=ordering_method,
                warnings=warnings,
            )
            status = TemporalLocalisationStatus.COMPLETE
            if warnings or ts_quality in {
                TimestampQuality.ABSENT,
                TimestampQuality.CONFLICTING,
            }:
                status = TemporalLocalisationStatus.PARTIAL
            if confidence < 0.35:
                status = TemporalLocalisationStatus.INCONCLUSIVE

            duration_ms = int((time.perf_counter() - started) * 1000)
            result = TemporalLocalisationResult(
                analysis_id=analysis_id,
                status=status,
                primary_failure_event_id=primary.id,
                primary_failure_type=primary.event_type.value,
                primary_failure_summary=(primary.message or "")[:500],
                downstream_symptom_event_ids=symptom_ids,
                upstream_context_event_ids=upstream,
                causal_precedence_links=links,
                events=ordered,
                ordering_method=ordering_method,
                timestamp_quality=ts_quality,
                confidence=confidence,
                warnings=warnings,
                missing_information=[],
                organization_id=organization_id,
                project_id=project_id,
                artifact_bundle_id=artifact_bundle_id,
                duration_ms=duration_ms,
            )
            logger.info(
                "temporal_localisation_completed",
                analysis_id=analysis_id,
                organization_id=organization_id,
                event_count=len(ordered),
                primary_event_id=primary.id,
                ordering_method=ordering_method.value,
                localisation_confidence=confidence,
                status=status.value,
                duration_ms=duration_ms,
            )
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("temporal_localisation_failed", analysis_id=analysis_id)
            return TemporalLocalisationResult(
                analysis_id=analysis_id,
                status=TemporalLocalisationStatus.FAILED,
                warnings=[type(exc).__name__],
                organization_id=organization_id,
                project_id=project_id,
                artifact_bundle_id=artifact_bundle_id,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )

    def _order_events(
        self,
        events: list[TemporalEvent],
    ) -> tuple[list[TemporalEvent], TemporalOrderingMethod, TimestampQuality, list[str]]:
        warnings: list[str] = []
        with_ts = [e for e in events if e.timestamp is not None]
        without_ts = [e for e in events if e.timestamp is None]

        if not with_ts:
            ordered = sorted(events, key=lambda e: e.sequence_index)
            for i, event in enumerate(ordered):
                event.sequence_index = i
            return (
                ordered,
                TemporalOrderingMethod.PARSER_SEQUENCE,
                TimestampQuality.ABSENT,
                ["timestamps_absent_using_parser_sequence"],
            )

        if without_ts:
            warnings.append("partial_timestamps_mixed_ordering")

        # Detect conflicting clocks within same job when sequence disagrees.
        conflicting = False
        by_job: dict[str, list[TemporalEvent]] = defaultdict(list)
        for event in with_ts:
            by_job[event.job_name or "__none__"].append(event)
        for group in by_job.values():
            sorted_ts = sorted(group, key=lambda e: e.timestamp or datetime.min)
            sorted_seq = sorted(group, key=lambda e: e.sequence_index)
            if [e.id for e in sorted_ts] != [e.id for e in sorted_seq]:
                # Allow small disagreements; mark conflicting when inverted pairs exist
                for a, b in zip(sorted_seq, sorted_seq[1:], strict=False):
                    if (
                        a.timestamp
                        and b.timestamp
                        and a.timestamp > b.timestamp
                        and a.sequence_index < b.sequence_index
                    ):
                        conflicting = True
                        break

        ts_quality = TimestampQuality.PRECISE
        if conflicting:
            ts_quality = TimestampQuality.CONFLICTING
            warnings.append("conflicting_timestamps")
        elif without_ts:
            ts_quality = TimestampQuality.COARSE

        # Partial order: within each job, sort by timestamp then sequence; across jobs keep parser seq.
        job_groups: dict[str, list[TemporalEvent]] = defaultdict(list)
        for event in events:
            job_groups[event.job_name or f"__seq_{event.sequence_index}"].append(event)

        ordered_events: list[TemporalEvent] = []
        # Preserve first-seen job order by min sequence_index
        job_order = sorted(
            job_groups.keys(),
            key=lambda k: min(e.sequence_index for e in job_groups[k]),
        )
        for job in job_order:
            group = job_groups[job]
            group_sorted = sorted(
                group,
                key=lambda e: (
                    e.timestamp is None,
                    e.timestamp or datetime.min,
                    e.sequence_index,
                ),
            )
            ordered_events.extend(group_sorted)

        for i, event in enumerate(ordered_events):
            event.sequence_index = i

        method = (
            TemporalOrderingMethod.MIXED
            if without_ts
            else TemporalOrderingMethod.TIMESTAMP
        )
        if conflicting:
            method = TemporalOrderingMethod.PARTIAL
        return ordered_events, method, ts_quality, warnings

    def _build_order_links(
        self,
        ordered: list[TemporalEvent],
        method: TemporalOrderingMethod,
    ) -> list[TemporalCausalLink]:
        links: list[TemporalCausalLink] = []
        derivation = (
            TemporalLinkDerivation.TEMPORAL_DETERMINISTIC
            if method == TemporalOrderingMethod.TIMESTAMP
            else TemporalLinkDerivation.TEMPORAL_HEURISTIC
        )
        # Within same job only — avoid false total order across parallel jobs.
        by_job: dict[str, list[TemporalEvent]] = defaultdict(list)
        for event in ordered:
            by_job[event.job_name or event.id].append(event)
        for group in by_job.values():
            for left, right in zip(group, group[1:], strict=False):
                links.append(
                    TemporalCausalLink(
                        id=str(uuid.uuid4()),
                        source_event_id=left.id,
                        target_event_id=right.id,
                        link_type=TemporalLinkType.OCCURRED_BEFORE,
                        derivation=derivation,
                        confidence=0.9 if derivation == TemporalLinkDerivation.TEMPORAL_DETERMINISTIC else 0.6,
                        explanation="Ordered within job by timestamp/sequence.",
                        supporting_event_ids=[left.id, right.id],
                        rule_id=RULE_ORDER,
                        rule_version=HEURISTIC_VERSION,
                        proven_causality=False,
                    )
                )
        return links

    def _build_parallel_links(self, ordered: list[TemporalEvent]) -> list[TemporalCausalLink]:
        jobs = {e.job_name for e in ordered if e.job_name}
        if len(jobs) < 2:
            return []
        # Mark first event of each pair of jobs as PARALLEL_WITH (partial order).
        representatives = {}
        for event in ordered:
            if event.job_name and event.job_name not in representatives:
                representatives[event.job_name] = event
        names = sorted(representatives.keys())
        links: list[TemporalCausalLink] = []
        for i, left_name in enumerate(names):
            for right_name in names[i + 1 :]:
                left = representatives[left_name]
                right = representatives[right_name]
                links.append(
                    TemporalCausalLink(
                        id=str(uuid.uuid4()),
                        source_event_id=left.id,
                        target_event_id=right.id,
                        link_type=TemporalLinkType.PARALLEL_WITH,
                        derivation=TemporalLinkDerivation.WORKFLOW_STRUCTURE,
                        confidence=0.5,
                        explanation="Jobs lack needs-edges; treated as potentially parallel.",
                        supporting_event_ids=[left.id, right.id],
                        rule_id=RULE_PARALLEL,
                        rule_version=HEURISTIC_VERSION,
                        proven_causality=False,
                    )
                )
        return links

    def _build_structure_links(self, ordered: list[TemporalEvent]) -> list[TemporalCausalLink]:
        links: list[TemporalCausalLink] = []
        by_step: dict[tuple[str | None, str | None], list[TemporalEvent]] = defaultdict(list)
        for event in ordered:
            if event.step_name:
                by_step[(event.job_name, event.step_name)].append(event)
        for group in by_step.values():
            if len(group) < 2:
                continue
            base = group[0]
            for other in group[1:]:
                links.append(
                    TemporalCausalLink(
                        id=str(uuid.uuid4()),
                        source_event_id=base.id,
                        target_event_id=other.id,
                        link_type=TemporalLinkType.SAME_STEP,
                        derivation=TemporalLinkDerivation.WORKFLOW_STRUCTURE,
                        confidence=0.85,
                        explanation="Events share job/step identity.",
                        supporting_event_ids=[base.id, other.id],
                        rule_id="TL-SAME-STEP-v1",
                        rule_version=HEURISTIC_VERSION,
                        proven_causality=False,
                    )
                )
        return links

    def _select_primary(
        self,
        ordered: list[TemporalEvent],
        failures: list[TemporalEvent],
    ) -> tuple[TemporalEvent, list[str], list[str]]:
        warnings: list[str] = []
        # Retry handling: if RETRY appears and a later non-failure succeeds in same step,
        # drop earlier transient errors for that step.
        retry_indices = [e.sequence_index for e in ordered if e.event_type == TemporalEventType.RETRY]
        suppressed: set[str] = set()
        for retry_idx in retry_indices:
            retry_event = next(e for e in ordered if e.sequence_index == retry_idx)
            step_key = (retry_event.job_name, retry_event.step_name)
            later_failures = [
                e
                for e in failures
                if e.sequence_index > retry_idx
                and (e.job_name, e.step_name) == step_key
            ]
            earlier_failures = [
                e
                for e in failures
                if e.sequence_index < retry_idx
                and (e.job_name, e.step_name) == step_key
            ]
            if not later_failures and earlier_failures:
                # Retry appears to have cleared the error (no later failure in step).
                for event in earlier_failures:
                    suppressed.add(event.id)
                warnings.append("retry_success_suppressed_transient_errors")
                # link
            elif later_failures and earlier_failures:
                # Keep earliest repeated causal error of highest priority.
                warnings.append("retry_repeated_failure_keep_earliest")

        candidates = [e for e in failures if e.id not in suppressed]
        if not candidates:
            candidates = failures

        # Prefer non-generic, high priority, earliest.
        non_generic = [e for e in candidates if not is_generic_downstream(e)]
        pool = non_generic or candidates
        pool_sorted = sorted(
            pool,
            key=lambda e: (-causal_priority(e), e.sequence_index),
        )
        primary = pool_sorted[0]

        # Equally early high-priority competitors
        peers = [
            e
            for e in pool_sorted
            if causal_priority(e) == causal_priority(primary)
            and e.sequence_index == primary.sequence_index
            and e.id != primary.id
        ]
        if peers:
            warnings.append("multiple_equally_early_errors")

        symptom_ids = [
            e.id
            for e in failures
            if e.id != primary.id
            and e.sequence_index >= primary.sequence_index
            and (is_generic_downstream(e) or causal_priority(e) < causal_priority(primary))
        ]
        return primary, symptom_ids, warnings

    def _confidence(
        self,
        *,
        primary: TemporalEvent,
        failures: list[TemporalEvent],
        ts_quality: TimestampQuality,
        ordering_method: TemporalOrderingMethod,
        warnings: list[str],
    ) -> float:
        score = 0.75
        score += 0.1 * (causal_priority(primary) / 100.0)
        if ts_quality == TimestampQuality.ABSENT:
            score -= 0.2
        elif ts_quality == TimestampQuality.CONFLICTING:
            score -= 0.25
        elif ts_quality == TimestampQuality.COARSE:
            score -= 0.1
        if ordering_method == TemporalOrderingMethod.PARSER_SEQUENCE:
            score -= 0.1
        if "multiple_equally_early_errors" in warnings:
            score -= 0.15
        if primary.job_name is None or primary.step_name is None:
            score -= 0.1
        if primary.extraction_confidence < 0.5:
            score -= 0.1
        if len(failures) == 1:
            score += 0.05
        return max(0.05, min(0.95, score))
