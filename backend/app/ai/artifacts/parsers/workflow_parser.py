"""GitHub Actions workflow YAML structured parser."""

from __future__ import annotations

import re
from typing import Any

import yaml

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
_SECRET_REF_RE = re.compile(r"\$\{\{\s*secrets\.([A-Za-z0-9_]+)\s*\}\}")
_ENV_REF_RE = re.compile(r"\$\{\{\s*env\.([A-Za-z0-9_]+)\s*\}\}")
_FAILED_HINT_RE = re.compile(r"(?i)\b(fail|failed|error|abort)\b")
_LOCAL_REUSABLE_RE = re.compile(r"^\./\.github/workflows/")


class WorkflowParser(StructuredArtifactParser):
    name = "workflow_parser"
    version = PARSER_VERSION

    def supports(self, kind: ArtifactKind) -> bool:
        return kind in {
            ArtifactKind.WORKFLOW_YAML,
            ArtifactKind.REUSABLE_WORKFLOW_YAML,
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

        try:
            parsed = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            errors.append(f"YAML parse error: {exc}")
            return StructuredParseResult(
                parser_name=self.name,
                parser_version=self.version,
                status=ParseStatus.FAILED,
                diagnostics=[
                    DiagnosticMessage(
                        severity="error",
                        code="yaml_parse_error",
                        message=str(exc),
                    )
                ],
                errors=errors,
                extraction_quality=0.0,
                raw_summary={"filename": filename},
            )

        if not isinstance(parsed, dict):
            errors.append("Workflow root must be a mapping")
            return StructuredParseResult(
                parser_name=self.name,
                parser_version=self.version,
                status=ParseStatus.FAILED,
                errors=errors,
                extraction_quality=0.0,
                raw_summary={"filename": filename, "root_type": type(parsed).__name__},
            )

        workflow_name = parsed.get("name")
        if not isinstance(workflow_name, str) or not workflow_name.strip():
            workflow_name = filename
        workflow_id = f"workflow:{workflow_name}"

        on_triggers = _normalise_triggers(parsed.get("on") or parsed.get(True))
        permissions = parsed.get("permissions")
        concurrency = parsed.get("concurrency")
        is_reusable = kind == ArtifactKind.REUSABLE_WORKFLOW_YAML or _has_workflow_call(
            parsed
        )

        entities.append(
            GraphEntityPreview(
                id=workflow_id,
                type="WORKFLOW",
                label=str(workflow_name),
                location=SourceLocation(path=filename, line_start=1),
                metadata={
                    "on": on_triggers,
                    "permissions": permissions,
                    "concurrency": concurrency,
                    "is_reusable": is_reusable,
                    "filename": filename,
                },
            )
        )

        # Top-level env
        _extract_env_entities(
            parsed.get("env"),
            parent_id=workflow_id,
            filename=filename,
            entities=entities,
            relationships=relationships,
            scope="workflow",
        )

        # Secret references anywhere in raw content
        secret_names = sorted(set(_SECRET_REF_RE.findall(content)))
        for secret_name in secret_names:
            secret_id = f"secret:{secret_name}"
            entities.append(
                GraphEntityPreview(
                    id=secret_id,
                    type="SECRET_REFERENCE",
                    label=secret_name,
                    location=SourceLocation(path=filename),
                    metadata={"expression": f"${{{{ secrets.{secret_name} }}}}"},
                )
            )
            relationships.append(
                GraphRelationshipPreview(
                    source_id=workflow_id,
                    target_id=secret_id,
                    type="REFERENCES",
                    confidence=1.0,
                    explanation=f"Workflow references secrets.{secret_name}",
                    deterministic=True,
                )
            )

        jobs = parsed.get("jobs")
        job_names: list[str] = []
        if isinstance(jobs, dict):
            for job_key, job_body in jobs.items():
                job_names.append(str(job_key))
                job_id = f"job:{job_key}"
                job_meta: dict[str, Any] = {"job_key": str(job_key)}
                if isinstance(job_body, dict):
                    if "if" in job_body:
                        job_meta["condition"] = job_body.get("if")
                    if "strategy" in job_body:
                        strategy = job_body.get("strategy")
                        job_meta["strategy"] = strategy
                        if isinstance(strategy, dict) and "matrix" in strategy:
                            job_meta["matrix"] = strategy.get("matrix")
                    if "permissions" in job_body:
                        job_meta["permissions"] = job_body.get("permissions")
                    if "concurrency" in job_body:
                        job_meta["concurrency"] = job_body.get("concurrency")
                    if "uses" in job_body:
                        job_meta["uses"] = job_body.get("uses")
                        uses_val = str(job_body.get("uses") or "")
                        action_id = f"action:{uses_val}"
                        entities.append(
                            GraphEntityPreview(
                                id=action_id,
                                type="ACTION_REF",
                                label=uses_val,
                                location=SourceLocation(path=filename),
                                metadata={
                                    "uses": uses_val,
                                    "reusable_local": bool(
                                        _LOCAL_REUSABLE_RE.match(uses_val)
                                    ),
                                    "scope": "job",
                                },
                            )
                        )
                        relationships.append(
                            GraphRelationshipPreview(
                                source_id=job_id,
                                target_id=action_id,
                                type="USES",
                                confidence=1.0,
                                explanation=f"Job {job_key} uses {uses_val}",
                                deterministic=True,
                            )
                        )
                    needs = job_body.get("needs")
                    if needs is not None:
                        job_meta["needs"] = needs
                        for needed in _as_list(needs):
                            relationships.append(
                                GraphRelationshipPreview(
                                    source_id=job_id,
                                    target_id=f"job:{needed}",
                                    type="NEEDS",
                                    confidence=1.0,
                                    explanation=f"Job {job_key} needs {needed}",
                                    deterministic=True,
                                )
                            )

                entities.append(
                    GraphEntityPreview(
                        id=job_id,
                        type="JOB",
                        label=str(job_key),
                        location=SourceLocation(path=filename),
                        metadata=job_meta,
                    )
                )
                relationships.append(
                    GraphRelationshipPreview(
                        source_id=workflow_id,
                        target_id=job_id,
                        type="CONTAINS",
                        confidence=1.0,
                        explanation=f"Workflow contains job {job_key}",
                        deterministic=True,
                    )
                )

                if not isinstance(job_body, dict):
                    warnings.append(f"Job {job_key} body is not a mapping")
                    continue

                _extract_env_entities(
                    job_body.get("env"),
                    parent_id=job_id,
                    filename=filename,
                    entities=entities,
                    relationships=relationships,
                    scope=f"job:{job_key}",
                )

                steps = job_body.get("steps")
                if not isinstance(steps, list):
                    continue
                for step_index, step in enumerate(steps):
                    if not isinstance(step, dict):
                        continue
                    step_name = step.get("name") or f"step-{step_index}"
                    step_id = f"step:{job_key}:{step_index}"
                    step_meta: dict[str, Any] = {
                        "index": step_index,
                        "job": str(job_key),
                    }
                    if "if" in step:
                        step_meta["condition"] = step.get("if")
                    if "id" in step:
                        step_meta["step_id"] = step.get("id")

                    entities.append(
                        GraphEntityPreview(
                            id=step_id,
                            type="STEP",
                            label=str(step_name),
                            location=SourceLocation(path=filename),
                            metadata=step_meta,
                        )
                    )
                    relationships.append(
                        GraphRelationshipPreview(
                            source_id=job_id,
                            target_id=step_id,
                            type="CONTAINS",
                            confidence=1.0,
                            explanation=f"Job {job_key} contains step {step_index}",
                            deterministic=True,
                        )
                    )

                    run_cmd = step.get("run")
                    if isinstance(run_cmd, str) and run_cmd.strip():
                        cmd_id = f"command:{job_key}:{step_index}"
                        entities.append(
                            GraphEntityPreview(
                                id=cmd_id,
                                type="COMMAND",
                                label=run_cmd.strip().splitlines()[0][:120],
                                location=SourceLocation(path=filename),
                                metadata={"run": run_cmd, "job": str(job_key)},
                            )
                        )
                        relationships.append(
                            GraphRelationshipPreview(
                                source_id=step_id,
                                target_id=cmd_id,
                                type="EXECUTES",
                                confidence=1.0,
                                explanation="Step executes shell command",
                                deterministic=True,
                            )
                        )
                        if _FAILED_HINT_RE.search(run_cmd) or _FAILED_HINT_RE.search(
                            str(step_name)
                        ):
                            evidence.append(
                                EvidenceCandidate(
                                    kind="failed_looking_step",
                                    text=run_cmd.strip()[:500],
                                    location=SourceLocation(path=filename),
                                    importance=0.7,
                                    metadata={
                                        "job": str(job_key),
                                        "step_index": step_index,
                                        "step_name": str(step_name),
                                    },
                                )
                            )

                    uses = step.get("uses")
                    if isinstance(uses, str) and uses.strip():
                        action_id = f"action:{uses}"
                        if not any(e.id == action_id for e in entities):
                            entities.append(
                                GraphEntityPreview(
                                    id=action_id,
                                    type="ACTION_REF",
                                    label=uses,
                                    location=SourceLocation(path=filename),
                                    metadata={
                                        "uses": uses,
                                        "reusable_local": bool(
                                            _LOCAL_REUSABLE_RE.match(uses)
                                        ),
                                        "scope": "step",
                                    },
                                )
                            )
                        relationships.append(
                            GraphRelationshipPreview(
                                source_id=step_id,
                                target_id=action_id,
                                type="USES",
                                confidence=1.0,
                                explanation=f"Step uses {uses}",
                                deterministic=True,
                            )
                        )

                    _extract_env_entities(
                        step.get("env"),
                        parent_id=step_id,
                        filename=filename,
                        entities=entities,
                        relationships=relationships,
                        scope=f"step:{job_key}:{step_index}",
                    )

                    # Inline secret refs in step fields
                    step_blob = yaml.safe_dump(step)
                    for secret_name in sorted(set(_SECRET_REF_RE.findall(step_blob))):
                        relationships.append(
                            GraphRelationshipPreview(
                                source_id=step_id,
                                target_id=f"secret:{secret_name}",
                                type="REFERENCES",
                                confidence=1.0,
                                explanation=f"Step references secrets.{secret_name}",
                                deterministic=True,
                            )
                        )
        else:
            warnings.append("Workflow has no jobs mapping")

        status = ParseStatus.SUCCESS
        if warnings and not job_names:
            status = ParseStatus.PARTIAL

        quality = 1.0 if status == ParseStatus.SUCCESS else 0.6
        if not job_names:
            quality = 0.3

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
                "workflow_name": workflow_name,
                "job_count": len(job_names),
                "jobs": job_names,
                "trigger_count": len(on_triggers),
                "triggers": on_triggers,
                "secret_reference_count": len(secret_names),
                "is_reusable": is_reusable,
                "has_permissions": permissions is not None,
                "has_concurrency": concurrency is not None,
            },
        )


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _normalise_triggers(on_value: Any) -> list[str]:
    if on_value is None:
        return []
    if isinstance(on_value, str):
        return [on_value]
    if isinstance(on_value, list):
        return [str(v) for v in on_value]
    if isinstance(on_value, dict):
        return [str(k) for k in on_value]
    return [str(on_value)]


def _has_workflow_call(parsed: dict[str, Any]) -> bool:
    # PyYAML may parse a bare `on:` / odd key as non-string; tolerate safely.
    on_value: Any = parsed.get("on")
    if on_value is None:
        for key, value in parsed.items():
            if key is True or key == "true":
                on_value = value
                break
    if isinstance(on_value, dict):
        return "workflow_call" in on_value
    if isinstance(on_value, list):
        return "workflow_call" in on_value
    if isinstance(on_value, str):
        return on_value == "workflow_call"
    return False


def _extract_env_entities(
    env_value: Any,
    *,
    parent_id: str,
    filename: str,
    entities: list[GraphEntityPreview],
    relationships: list[GraphRelationshipPreview],
    scope: str,
) -> None:
    if not isinstance(env_value, dict):
        return
    for key, value in env_value.items():
        env_id = f"env:{scope}:{key}"
        entities.append(
            GraphEntityPreview(
                id=env_id,
                type="ENVIRONMENT_VARIABLE",
                label=str(key),
                location=SourceLocation(path=filename),
                metadata={"value_preview": str(value)[:200], "scope": scope},
            )
        )
        relationships.append(
            GraphRelationshipPreview(
                source_id=parent_id,
                target_id=env_id,
                type="CONTAINS",
                confidence=1.0,
                explanation=f"{scope} declares env {key}",
                deterministic=True,
            )
        )
        for env_ref in _ENV_REF_RE.findall(str(value)):
            relationships.append(
                GraphRelationshipPreview(
                    source_id=env_id,
                    target_id=f"env_ref:{env_ref}",
                    type="REFERENCES",
                    confidence=0.9,
                    explanation=f"Env {key} references env.{env_ref}",
                    deterministic=True,
                )
            )
