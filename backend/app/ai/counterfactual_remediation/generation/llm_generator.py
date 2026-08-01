"""Structured LLM remediation generator with strict schema validation."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.ai.counterfactual_remediation.generation._helpers import (
    as_dict,
    as_list,
    contains_wildcard,
    first_str,
    get_source_fragment,
)
from app.ai.counterfactual_remediation.generation.prompt import (
    COUNTERFACTUAL_REMEDIATION_JSON_SCHEMA,
    build_remediation_prompt,
)
from app.ai.counterfactual_remediation.safety import (
    contains_secret_material,
    mask_for_context,
    sanitize_untrusted_instructions,
)
from app.domain.counterfactual_remediation.enums import (
    CounterfactualCandidateStatus,
    CounterfactualChangeType,
    ExpectedFailureConditionStatus,
)
from app.domain.counterfactual_remediation.generation_enums import (
    RemediationGenerationStatus,
    RemediationGeneratorType,
)
from app.domain.counterfactual_remediation.generation_models import (
    RemediationGenerationContext,
    RemediationGenerationResult,
)
from app.domain.counterfactual_remediation.generation_versions import (
    COUNTERFACTUAL_REMEDIATION_PROMPT_VERSION,
    COUNTERFACTUAL_REMEDIATION_SCHEMA_VERSION,
)
from app.domain.counterfactual_remediation.models import (
    CounterfactualChange,
    CounterfactualRemediationCandidate,
    RemediationCounterfactualState,
)

logger = logging.getLogger(__name__)

LlmCall = Callable[[str], dict[str, Any] | str]


class LLMCounterfactualRemediationGenerator:
    """LLM structured candidate generator — soft-fail, mock-friendly."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        llm_call: LlmCall | None = None,
        max_candidates: int = 2,
        max_calls: int = 3,
    ) -> None:
        self._enabled = enabled
        self._llm_call = llm_call
        self._max = max(1, max_candidates)
        self._max_calls = max(1, max_calls)
        self._calls = 0
        self.prompt_version = COUNTERFACTUAL_REMEDIATION_PROMPT_VERSION
        self.schema_version = COUNTERFACTUAL_REMEDIATION_SCHEMA_VERSION

    def generate(self, context: RemediationGenerationContext) -> RemediationGenerationResult:
        started = datetime.now(UTC)
        if not self._enabled:
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.LLM_STRUCTURED,
                status=RemediationGenerationStatus.DISABLED,
                duration_ms=0,
            )
        if self._llm_call is None:
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.LLM_STRUCTURED,
                status=RemediationGenerationStatus.DISABLED,
                warnings=["no_llm_provider"],
                duration_ms=self._ms(started),
            )
        if self._calls >= self._max_calls:
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.LLM_STRUCTURED,
                status=RemediationGenerationStatus.FAILED,
                errors=["llm_call_budget_exceeded"],
                duration_ms=self._ms(started),
            )

        prompt = build_remediation_prompt(self._context_payload(context))
        try:
            self._calls += 1
            raw = self._llm_call(prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("llm_remediation_call_failed error=%s", type(exc).__name__)
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.LLM_STRUCTURED,
                status=RemediationGenerationStatus.FAILED,
                errors=[f"llm_call_failed:{type(exc).__name__}"],
                duration_ms=self._ms(started),
            )

        parsed, errors = self._parse_and_validate(raw)
        if errors and not parsed:
            return RemediationGenerationResult(
                generator=RemediationGeneratorType.LLM_STRUCTURED,
                status=RemediationGenerationStatus.FAILED,
                errors=errors,
                duration_ms=self._ms(started),
            )

        candidates: list[CounterfactualRemediationCandidate] = []
        warnings = list(errors)
        for item in parsed[: self._max]:
            built, reject_reasons = self._build_candidate(item, context)
            if built is None:
                warnings.extend(reject_reasons)
                continue
            candidates.append(built)

        if not candidates:
            status = RemediationGenerationStatus.NO_APPLICABLE_TEMPLATE
        elif warnings:
            status = RemediationGenerationStatus.PARTIAL
        else:
            status = RemediationGenerationStatus.COMPLETE
        return RemediationGenerationResult(
            generator=RemediationGeneratorType.LLM_STRUCTURED,
            status=status,
            candidates=candidates,
            warnings=warnings,
            duration_ms=self._ms(started),
            generator_version=self.schema_version,
        )

    def _context_payload(self, context: RemediationGenerationContext) -> dict[str, Any]:
        fragment = get_source_fragment(context.current_state, context.source_fragment) or ""
        fragment = sanitize_untrusted_instructions(mask_for_context(fragment))
        return {
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "analysis_id": context.analysis_id,
            "hypothesis_id": context.hypothesis_id,
            "hypothesis_unverified": True,
            "causal_claim": context.causal_claim,
            "category": context.category,
            "ranking_score": context.ranking_score,
            "current_state_fragment": fragment[:4000],
            "content_hash": context.content_hash,
            "failure_condition_summary": context.failure_condition_summary,
            "blocking_constraints": [
                as_dict(c).get("constraint_key") or as_dict(c).get("id")
                for c in context.blocking_constraints[:30]
            ],
            "valid_artifact_ids": list(context.valid_artifact_ids)[:40],
            "valid_graph_node_ids": list(context.valid_graph_node_ids)[:40],
            "valid_evidence_ids": list(context.valid_evidence_ids)[:40],
            "valid_template_ids": list(context.valid_template_ids)[:40],
            "allowed_change_types": list(context.allowed_change_types)[:40],
            "minimal_change_plan": as_dict(context.plan),
            "schema": COUNTERFACTUAL_REMEDIATION_JSON_SCHEMA,
        }

    def _parse_and_validate(
        self, raw: dict[str, Any] | str
    ) -> tuple[list[dict[str, Any]], list[str]]:
        errors: list[str] = []
        data: Any = raw
        if isinstance(raw, str):
            text = raw.strip()
            fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
            if fence:
                text = fence.group(1)
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                return [], [f"malformed_json:{exc}"]
        if not isinstance(data, dict):
            return [], ["root_not_object"]
        # Reject unknown top-level keys.
        unknown = set(data) - set(COUNTERFACTUAL_REMEDIATION_JSON_SCHEMA["properties"])
        if unknown:
            errors.append(f"unknown_top_level_keys:{sorted(unknown)}")
        items = data.get("candidates")
        if not isinstance(items, list):
            return [], errors + ["candidates_not_list"]
        cleaned: list[dict[str, Any]] = []
        allowed_candidate_keys = set(
            COUNTERFACTUAL_REMEDIATION_JSON_SCHEMA["properties"]["candidates"]["items"][
                "properties"
            ]
        )
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"candidate_{idx}_not_object")
                continue
            extra = set(item) - allowed_candidate_keys
            if extra:
                errors.append(f"candidate_{idx}_unknown_fields:{sorted(extra)}")
                continue
            for req in COUNTERFACTUAL_REMEDIATION_JSON_SCHEMA["properties"]["candidates"]["items"][
                "required"
            ]:
                if req not in item:
                    errors.append(f"candidate_{idx}_missing:{req}")
                    break
            else:
                cleaned.append(item)
        return cleaned, errors

    def _build_candidate(
        self,
        item: dict[str, Any],
        context: RemediationGenerationContext,
    ) -> tuple[CounterfactualRemediationCandidate | None, list[str]]:
        reasons: list[str] = []
        hyp_id = str(item.get("hypothesis_id") or "")
        if hyp_id and hyp_id != context.hypothesis_id:
            return None, ["hypothesis_id_mismatch"]

        template_id = item.get("template_id")
        if (
            template_id
            and context.valid_template_ids
            and str(template_id) not in context.valid_template_ids
        ):
            return None, [f"invented_template_id:{template_id}"]

        changes_out: list[CounterfactualChange] = []
        candidate_id = str(uuid4())
        for change_raw in as_list(item.get("artifact_changes")):
            if not isinstance(change_raw, dict):
                reasons.append("change_not_object")
                continue
            artifact_id = first_str(change_raw.get("artifact_id"))
            if (
                artifact_id
                and context.valid_artifact_ids
                and artifact_id not in context.valid_artifact_ids
            ):
                reasons.append(f"invented_artifact_id:{artifact_id}")
                continue
            original = change_raw.get("original_fragment")
            proposed = change_raw.get("proposed_fragment")
            if not isinstance(original, str) or not isinstance(proposed, str):
                reasons.append("missing_fragments")
                continue
            if contains_secret_material(proposed) or contains_wildcard(proposed):
                reasons.append("unsafe_proposed_fragment")
                continue
            for nid in as_list(change_raw.get("graph_node_ids")):
                if context.valid_graph_node_ids and str(nid) not in context.valid_graph_node_ids:
                    reasons.append(f"invented_graph_node:{nid}")
                    break
            else:
                for eid in as_list(change_raw.get("evidence_ids")):
                    if context.valid_evidence_ids and str(eid) not in context.valid_evidence_ids:
                        reasons.append(f"invented_evidence_id:{eid}")
                        break
                else:
                    ctype_raw = str(change_raw.get("change_type") or "UNKNOWN")
                    try:
                        ctype = CounterfactualChangeType(ctype_raw)
                    except ValueError:
                        reasons.append(f"invalid_change_type:{ctype_raw}")
                        continue
                    if (
                        context.allowed_change_types
                        and ctype.value not in context.allowed_change_types
                    ):
                        reasons.append(f"disallowed_change_type:{ctype.value}")
                        continue
                    changes_out.append(
                        CounterfactualChange(
                            id=str(uuid4()),
                            candidate_id=candidate_id,
                            artifact_id=artifact_id,
                            artifact_type=change_raw.get("artifact_type"),
                            source_path=first_str(change_raw.get("source_path")),
                            change_type=ctype,
                            target_property=first_str(change_raw.get("target_property")),
                            original_fragment=original,
                            proposed_fragment=proposed,
                            expected_effect=first_str(change_raw.get("expected_effect")) or "",
                            rationale="LLM structured proposal (unverified)",
                            evidence_ids=[str(x) for x in as_list(change_raw.get("evidence_ids"))],
                            graph_node_ids=[
                                str(x) for x in as_list(change_raw.get("graph_node_ids"))
                            ],
                            limitations=[
                                "candidates_are_not_verified",
                                "llm_untrusted_until_validated",
                            ],
                        )
                    )
        if not changes_out:
            return None, reasons or ["no_valid_changes"]

        limitations = [str(x) for x in as_list(item.get("limitations"))]
        if "candidates_are_not_verified" not in limitations:
            limitations.append("candidates_are_not_verified")
        candidate = CounterfactualRemediationCandidate(
            id=candidate_id,
            remediation_run_id=context.remediation_run_id,
            organization_id=context.organization_id,
            project_id=context.project_id,
            incident_id=context.incident_id,
            analysis_id=context.analysis_id,
            hypothesis_id=context.hypothesis_id,
            candidate_key=str(item.get("candidate_key") or f"{context.hypothesis_id}:llm"),
            title=str(item.get("title") or "LLM remediation candidate"),
            summary=str(item.get("summary") or "Structured LLM candidate. Not verified."),
            artifact_type=changes_out[0].artifact_type,
            affected_artifact_ids=[
                a for a in {c.artifact_id for c in changes_out if c.artifact_id}
            ],
            primary_artifact_id=changes_out[0].artifact_id,
            target_paths=[p for p in {c.source_path for c in changes_out if c.source_path}],
            change_types=[c.change_type for c in changes_out],
            changes=changes_out,
            current_state_snapshot=context.current_state,
            counterfactual_state_snapshot=RemediationCounterfactualState(
                candidate_id=candidate_id,
                expected_failure_condition_status=ExpectedFailureConditionStatus.EXPECTED_REMOVED,
                assumptions=["llm_structured_proposal"],
            ),
            expected_effects=[str(x) for x in as_list(item.get("expected_effects"))][:20],
            expected_preserved_behaviors=[
                str(x) for x in as_list(item.get("expected_preserved_behaviors"))
            ][:20],
            assumptions=[str(x) for x in as_list(item.get("assumptions"))][:20],
            limitations=limitations[:20],
            generator_type=RemediationGeneratorType.LLM_STRUCTURED.value,
            generator_name="llm_counterfactual_remediation_generator",
            generator_version=self.schema_version,
            template_id=str(template_id) if template_id else None,
            status=CounterfactualCandidateStatus.STRUCTURED,
        )
        return candidate, reasons

    @staticmethod
    def _ms(started: datetime) -> int:
        return int((datetime.now(UTC) - started).total_seconds() * 1000)
