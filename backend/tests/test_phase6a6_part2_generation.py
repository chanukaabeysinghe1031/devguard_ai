"""Phase 6A.6 Part 2 — generation safety and orchestration tests (fast, no LLM network)."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from uuid import uuid4

from app.ai.counterfactual_remediation.generation.deduplicator import (
    RemediationCandidateDeduplicator,
)
from app.ai.counterfactual_remediation.generation.generation_service import (
    CounterfactualRemediationGenerationService,
)
from app.ai.counterfactual_remediation.generation.patch_renderer import (
    RemediationPatchRenderer,
)
from app.ai.counterfactual_remediation.generation.prioritiser import (
    RemediationCandidatePrioritiser,
)
from app.ai.counterfactual_remediation.generation.reference_validator import (
    RemediationReferenceValidator,
)
from app.ai.counterfactual_remediation.generation.risk_analyzer import RemediationRiskAnalyzer
from app.ai.counterfactual_remediation.generation.rule_generator import (
    RuleBasedRemediationGenerator,
)
from app.ai.counterfactual_remediation.template_registry import RemediationTemplateRegistry
from app.application.services.analysis_execution_service import AnalysisExecutionService
from app.domain.counterfactual_remediation.enums import (
    CounterfactualCandidateStatus,
    CounterfactualChangeType,
    CounterfactualRemediationRunStatus,
)
from app.domain.counterfactual_remediation.generation_enums import (
    CandidatePriorityStatus,
    RemediationGeneratorType,
)
from app.domain.counterfactual_remediation.generation_models import (
    RemediationGenerationContext,
)
from app.domain.counterfactual_remediation.models import (
    CounterfactualChange,
    CounterfactualRemediationCandidate,
    CounterfactualRemediationRun,
)


def _settings(**flags: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "rule_remediation_generation_enabled": False,
        "llm_remediation_generation_enabled": False,
        "remediation_risk_analysis_enabled": True,
        "remediation_side_effect_analysis_enabled": True,
        "remediation_ranking_enabled": True,
        "remediation_deduplication_enabled": True,
        "remediation_diversity_enabled": True,
        "remediation_patch_rendering_enabled": True,
        "remediation_rollback_generation_enabled": True,
        "remediation_reference_validation_enabled": True,
        "remediation_constraint_validation_enabled": True,
        "max_rule_candidates_per_hypothesis": 3,
        "max_llm_candidates_per_hypothesis": 2,
        "max_final_candidates_per_hypothesis": 3,
        "max_total_final_candidates": 8,
        "max_candidate_patch_characters": 30_000,
        "max_candidate_changed_lines": 200,
        "max_remediation_llm_calls_per_analysis": 3,
        "max_rollback_steps_per_candidate": 20,
        "remediation_duplicate_similarity_threshold": 0.88,
        "remediation_high_risk_threshold": 0.70,
        "remediation_reject_risk_threshold": 0.90,
        "remediation_tie_epsilon": 0.02,
    }
    defaults.update(flags)
    return SimpleNamespace(**defaults)


def _ctx(**overrides: object) -> RemediationGenerationContext:
    data: dict[str, object] = {
        "organization_id": str(uuid4()),
        "project_id": str(uuid4()),
        "incident_id": str(uuid4()),
        "analysis_id": str(uuid4()),
        "hypothesis_id": str(uuid4()),
        "remediation_run_id": str(uuid4()),
        "valid_artifact_ids": ["art-1"],
        "valid_template_ids": [
            "iam.add_scoped_missing_action",
            "iam.correct_assumed_role_reference",
            "gha.correct_secret_reference_name",
        ],
        "current_state": {
            "artifact_id": "art-1",
            "artifact_type": "IAM_POLICY",
            "source_path": "iam/policy.json",
            "source_fragment": json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": "s3:GetObject",
                            "Resource": "arn:aws:s3:::bucket/*",
                        }
                    ],
                },
                indent=2,
            ),
            "current_values": {
                "missing_action": "s3:PutObject",
                "resource": "arn:aws:s3:::bucket/key",
                "principal": "arn:aws:iam::123456789012:role/deploy",
            },
        },
        "eligible_templates": [],
    }
    data.update(overrides)
    if not data["eligible_templates"]:
        registry = RemediationTemplateRegistry()
        data["eligible_templates"] = [
            t for t in registry.all_templates() if t.template_id == "iam.add_scoped_missing_action"
        ]
    return RemediationGenerationContext(**data)  # type: ignore[arg-type]


def test_flags_off_no_generation() -> None:
    run = CounterfactualRemediationRun(
        id=str(uuid4()),
        organization_id=str(uuid4()),
        project_id=str(uuid4()),
        incident_id=str(uuid4()),
        analysis_id=str(uuid4()),
        status=CounterfactualRemediationRunStatus.COMPLETE,
    )
    service = CounterfactualRemediationGenerationService(_settings())
    result = service.run(
        run,
        skeleton_candidates=[],
        generation_contexts=[_ctx()],
    )
    assert isinstance(result, tuple) and len(result) == 2
    first, second = result
    # Accept either (candidates, meta) or (run, candidates).
    if isinstance(second, dict):
        candidates, meta = first, second
        assert (
            candidates == []
            or meta.get("generation_enabled") is False
            or meta.get("status") == "DISABLED"
        )
    else:
        out_run, candidates = first, second
        assert candidates == []
        assert not service.any_generation_enabled() or "disabled" in str(out_run.warnings).lower()
    assert hasattr(AnalysisExecutionService, "_maybe_run_phase6a6_counterfactual_generation")


def test_rule_missing_iam_action_narrow_patch() -> None:
    gen = RuleBasedRemediationGenerator(enabled=True)
    result = gen.generate(_ctx())
    assert result.candidates
    cand = next(
        c for c in result.candidates if c.status == CounterfactualCandidateStatus.STRUCTURED
    )
    assert any("s3:PutObject" in (c.proposed_fragment or "") for c in cand.changes)
    assert 'Action": "*"' not in (cand.changes[0].proposed_fragment or "")


def test_rule_wrong_role_update_role() -> None:
    registry = RemediationTemplateRegistry()
    tmpl = registry.get("iam.correct_assumed_role_reference")
    assert tmpl is not None
    original = "permissions:\n  id-token: write\n  role: arn:aws:iam::123456789012:role/wrong\n"
    ctx = _ctx(
        eligible_templates=[tmpl],
        current_state={
            "artifact_id": "art-1",
            "source_path": ".github/workflows/deploy.yml",
            "source_fragment": original,
            "current_values": {
                "current_role": "arn:aws:iam::123456789012:role/wrong",
                "expected_role": "arn:aws:iam::123456789012:role/correct",
            },
        },
    )
    result = RuleBasedRemediationGenerator(enabled=True).generate(ctx)
    structured = [
        c for c in result.candidates if c.status == CounterfactualCandidateStatus.STRUCTURED
    ]
    assert structured
    change = structured[0].changes[0]
    assert change.change_type == CounterfactualChangeType.UPDATE_ROLE
    assert "role/correct" in (change.proposed_fragment or "")


def test_wildcard_rejected() -> None:
    ctx = _ctx()
    state = dict(ctx.current_state)  # type: ignore[arg-type]
    values = dict(state["current_values"])
    values["missing_action"] = "s3:*"
    # Avoid incidental * in original fragment confusing assertions.
    state["source_fragment"] = json.dumps({"Version": "2012-10-17", "Statement": []}, indent=2)
    state["current_values"] = values
    ctx.current_state = state
    result = RuleBasedRemediationGenerator(enabled=True).generate(ctx)
    if result.candidates:
        assert all(c.status == CounterfactualCandidateStatus.REJECTED for c in result.candidates)
        assert any("wildcard" in " ".join(c.assumptions) for c in result.candidates)
    else:
        assert "iam.add_scoped_missing_action" in (result.rejected_template_ids or [])


def test_explicit_deny_blocks_identity_add() -> None:
    ctx = _ctx()
    state = dict(ctx.current_state)  # type: ignore[arg-type]
    values = dict(state["current_values"])
    values["explicit_denies"] = True
    state["source_fragment"] = json.dumps({"Version": "2012-10-17", "Statement": []}, indent=2)
    state["current_values"] = values
    ctx.current_state = state
    result = RuleBasedRemediationGenerator(enabled=True).generate(ctx)
    if result.candidates:
        assert all(c.status == CounterfactualCandidateStatus.REJECTED for c in result.candidates)
        assert any("explicit_deny" in " ".join(c.assumptions) for c in result.candidates)
    else:
        assert "iam.add_scoped_missing_action" in (result.rejected_template_ids or [])


def test_secret_reference_name_only() -> None:
    registry = RemediationTemplateRegistry()
    tmpl = registry.get("gha.correct_secret_reference_name")
    assert tmpl is not None
    original = "env:\n  TOKEN: ${{ secrets.OLD_NAME }}\n"
    ctx = _ctx(
        eligible_templates=[tmpl],
        current_state={
            "artifact_id": "art-1",
            "source_path": ".github/workflows/ci.yml",
            "source_fragment": original,
            "current_values": {
                "secret_reference": "secrets.OLD_NAME",
                "expected_secret_name": "NEW_NAME",
            },
        },
    )
    result = RuleBasedRemediationGenerator(enabled=True).generate(ctx)
    assert result.candidates
    proposed = result.candidates[0].changes[0].proposed_fragment or ""
    assert "secrets.NEW_NAME" in proposed
    assert "AKIA" not in proposed


def test_fabricated_artifact_id_rejected() -> None:
    candidate = CounterfactualRemediationCandidate(
        id=str(uuid4()),
        remediation_run_id=str(uuid4()),
        organization_id=str(uuid4()),
        project_id=str(uuid4()),
        incident_id=str(uuid4()),
        analysis_id=str(uuid4()),
        hypothesis_id=str(uuid4()),
        affected_artifact_ids=["fabricated-999"],
        primary_artifact_id="fabricated-999",
        changes=[
            CounterfactualChange(
                id=str(uuid4()),
                artifact_id="fabricated-999",
                change_type=CounterfactualChangeType.UPDATE_VALUE,
            )
        ],
    )
    result = RemediationReferenceValidator().validate(candidate, valid_artifact_ids=["art-1"])
    status = result["status"] if isinstance(result, dict) else getattr(result, "status", None)
    errors = result["errors"] if isinstance(result, dict) else getattr(result, "errors", [])
    assert str(status) in {"REJECTED", "INVALID", "FAILED"} or errors
    assert any("fabricated" in str(e).lower() or "artifact" in str(e).lower() for e in errors) or (
        str(status) != "VALID"
    )


def test_patch_renderer_difflib_original_not_mutated() -> None:
    original = '{\n  "a": 1\n}\n'
    proposed = '{\n  "a": 2\n}\n'
    original_copy = copy.copy(original)
    rendered = RemediationPatchRenderer().render(
        original_fragment=original,
        proposed_fragment=proposed,
        source_path="policy.json",
    )
    assert original == original_copy
    assert rendered.normalized_diff
    assert rendered.content_hash_before
    assert rendered.content_hash_after


def test_risk_analyzer_wildcard_and_permission() -> None:
    candidate = CounterfactualRemediationCandidate(
        id=str(uuid4()),
        remediation_run_id=str(uuid4()),
        organization_id=str(uuid4()),
        project_id=str(uuid4()),
        incident_id=str(uuid4()),
        analysis_id=str(uuid4()),
        hypothesis_id=str(uuid4()),
        change_types=[CounterfactualChangeType.UPDATE_PERMISSION],
        changes=[
            CounterfactualChange(
                id=str(uuid4()),
                change_type=CounterfactualChangeType.UPDATE_PERMISSION,
                proposed_fragment='{"Action":"*","Resource":"*"}',
            )
        ],
    )
    risk = RemediationRiskAnalyzer().analyse(candidate)
    assert risk.component_scores.get("wildcard_access", 0) >= 0.9 or risk.overall_risk_score >= 0.7


def test_dedupe_merges_rule_and_llm() -> None:
    shared_kwargs = {
        "remediation_run_id": str(uuid4()),
        "organization_id": str(uuid4()),
        "project_id": str(uuid4()),
        "incident_id": str(uuid4()),
        "analysis_id": str(uuid4()),
        "hypothesis_id": str(uuid4()),
        "template_id": "iam.add_scoped_missing_action",
        "affected_artifact_ids": ["art-1"],
        "change_types": [CounterfactualChangeType.UPDATE_PERMISSION],
        "summary": "add action",
        "title": "add action",
        "changes": [
            CounterfactualChange(
                id=str(uuid4()),
                change_type=CounterfactualChangeType.UPDATE_PERMISSION,
                target_property="Statement",
                proposed_fragment='{"Action":"s3:PutObject"}',
                original_fragment="{}",
                normalized_diff="@@ -1 +1 @@\n-a\n+b\n",
            )
        ],
    }
    rule = CounterfactualRemediationCandidate(
        id=str(uuid4()),
        generator_type=RemediationGeneratorType.RULE_TEMPLATE.value,
        generator_name="rule",
        **shared_kwargs,  # type: ignore[arg-type]
    )
    llm = CounterfactualRemediationCandidate(
        id=str(uuid4()),
        generator_type=RemediationGeneratorType.LLM_STRUCTURED.value,
        generator_name="llm",
        **shared_kwargs,  # type: ignore[arg-type]
    )
    merged = RemediationCandidateDeduplicator().deduplicate([rule, llm])
    assert len(merged) == 1
    assert any("also_from" in a for a in merged[0].assumptions)


def test_prioritiser_prefers_wrong_role_over_policy_broaden() -> None:
    hyp = str(uuid4())
    role = CounterfactualRemediationCandidate(
        id="role-cand",
        remediation_run_id=str(uuid4()),
        organization_id=str(uuid4()),
        project_id=str(uuid4()),
        incident_id=str(uuid4()),
        analysis_id=str(uuid4()),
        hypothesis_id=hyp,
        candidate_key="role",
        change_types=[CounterfactualChangeType.UPDATE_ROLE],
        changes=[
            CounterfactualChange(
                id=str(uuid4()),
                change_type=CounterfactualChangeType.UPDATE_ROLE,
                proposed_fragment="role: correct",
            )
        ],
        primary_artifact_id="art-1",
        changed_file_count=1,
        changed_line_count=1,
        risk_score=0.1,
        blast_radius="LOCAL",
        rollback_plan={"rollback_steps": [{"step": 1}]},
    )
    broad = CounterfactualRemediationCandidate(
        id="policy-cand",
        remediation_run_id=str(uuid4()),
        organization_id=str(uuid4()),
        project_id=str(uuid4()),
        incident_id=str(uuid4()),
        analysis_id=str(uuid4()),
        hypothesis_id=hyp,
        candidate_key="policy",
        change_types=[CounterfactualChangeType.UPDATE_PERMISSION],
        changes=[
            CounterfactualChange(
                id=str(uuid4()),
                change_type=CounterfactualChangeType.UPDATE_PERMISSION,
                proposed_fragment='{"Action":"*"}',
            )
        ],
        primary_artifact_id="art-1",
        changed_file_count=1,
        changed_line_count=20,
        risk_score=0.5,
        blast_radius="LIMITED",
        rollback_plan={"rollback_steps": [{"step": 1}]},
    )
    result = RemediationCandidatePrioritiser().prioritise([broad, role])
    assert result.ordered_candidate_ids[0] == "role-cand"
    assert role.priority_status == CandidatePriorityStatus.PRIORITY_CANDIDATE.value


def test_no_safe_candidate_path() -> None:
    unsafe = CounterfactualRemediationCandidate(
        id="unsafe",
        remediation_run_id=str(uuid4()),
        organization_id=str(uuid4()),
        project_id=str(uuid4()),
        incident_id=str(uuid4()),
        analysis_id=str(uuid4()),
        hypothesis_id=str(uuid4()),
        status=CounterfactualCandidateStatus.UNSAFE,
        risk_score=0.95,
        risk_level="CRITICAL",
        changes=[],
    )
    result = RemediationCandidatePrioritiser().prioritise([unsafe])
    assert result.no_safe_candidate is True
