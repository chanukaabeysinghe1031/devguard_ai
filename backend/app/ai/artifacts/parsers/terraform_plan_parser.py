"""Terraform plan JSON structured parser."""

from __future__ import annotations

import json
from typing import Any

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


class TerraformPlanParser(StructuredArtifactParser):
    name = "terraform_plan_parser"
    version = PARSER_VERSION

    def supports(self, kind: ArtifactKind) -> bool:
        return kind == ArtifactKind.TERRAFORM_PLAN_JSON

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
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSON: {exc}")
            diagnostics.append(
                DiagnosticMessage(
                    severity="error",
                    code="invalid_plan_json",
                    message=str(exc),
                )
            )
            return StructuredParseResult(
                parser_name=self.name,
                parser_version=self.version,
                status=ParseStatus.FAILED,
                diagnostics=diagnostics,
                errors=errors,
                extraction_quality=0.0,
                raw_summary={"filename": filename},
            )

        if not isinstance(parsed, dict):
            errors.append("Terraform plan root must be a JSON object")
            diagnostics.append(
                DiagnosticMessage(
                    severity="error",
                    code="invalid_plan_root",
                    message="Expected object root with resource_changes",
                )
            )
            return StructuredParseResult(
                parser_name=self.name,
                parser_version=self.version,
                status=ParseStatus.FAILED,
                diagnostics=diagnostics,
                errors=errors,
                extraction_quality=0.0,
                raw_summary={"filename": filename, "root_type": type(parsed).__name__},
            )

        plan_id = f"plan:{filename}"
        entities.append(
            GraphEntityPreview(
                id=plan_id,
                type="TERRAFORM_PLAN",
                label=filename,
                location=SourceLocation(path=filename),
                metadata={
                    "format_version": parsed.get("format_version"),
                    "terraform_version": parsed.get("terraform_version"),
                },
            )
        )

        resource_changes = parsed.get("resource_changes")
        change_counts: dict[str, int] = {
            "create": 0,
            "update": 0,
            "delete": 0,
            "replace": 0,
            "no-op": 0,
            "other": 0,
        }

        if resource_changes is None:
            warnings.append("resource_changes missing")
            diagnostics.append(
                DiagnosticMessage(
                    severity="warning",
                    code="missing_resource_changes",
                    message="Plan JSON lacks resource_changes array",
                )
            )
            status = ParseStatus.PARTIAL
        elif not isinstance(resource_changes, list):
            errors.append("resource_changes must be an array")
            diagnostics.append(
                DiagnosticMessage(
                    severity="error",
                    code="invalid_resource_changes",
                    message="resource_changes must be a list",
                )
            )
            status = ParseStatus.FAILED
            resource_changes = []
        else:
            status = ParseStatus.SUCCESS
            for index, change in enumerate(resource_changes):
                if not isinstance(change, dict):
                    warnings.append(f"Skipping non-object resource_change[{index}]")
                    continue
                address = str(change.get("address") or f"unknown[{index}]")
                raw_change = change.get("change")
                change_body = raw_change if isinstance(raw_change, dict) else {}
                actions = _as_str_list(change_body.get("actions"))
                action_label = _classify_actions(actions)
                change_counts[action_label] = change_counts.get(action_label, 0) + 1

                entity_id = f"plan_resource:{address}"
                entities.append(
                    GraphEntityPreview(
                        id=entity_id,
                        type="PLAN_RESOURCE_CHANGE",
                        label=address,
                        location=SourceLocation(path=filename),
                        metadata={
                            "address": address,
                            "mode": change.get("mode"),
                            "type": change.get("type"),
                            "name": change.get("name"),
                            "provider_name": change.get("provider_name"),
                            "actions": actions,
                            "action_class": action_label,
                        },
                    )
                )
                relationships.append(
                    GraphRelationshipPreview(
                        source_id=plan_id,
                        target_id=entity_id,
                        type="CONTAINS",
                        confidence=1.0,
                        explanation=f"Plan contains change for {address}",
                        deterministic=True,
                    )
                )
                if action_label in {"delete", "replace", "update"}:
                    evidence.append(
                        EvidenceCandidate(
                            kind="plan_resource_change",
                            text=f"{address}: {', '.join(actions) or action_label}",
                            location=SourceLocation(path=filename),
                            importance=0.8 if action_label in {"delete", "replace"} else 0.6,
                            metadata={"address": address, "actions": actions},
                        )
                    )

        quality = (
            0.9
            if status == ParseStatus.SUCCESS
            else (0.4 if status == ParseStatus.PARTIAL else 0.0)
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
                "resource_change_count": (
                    len(resource_changes) if isinstance(resource_changes, list) else 0
                ),
                "change_counts": change_counts,
                "format_version": parsed.get("format_version"),
            },
        )


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if value is None:
        return []
    return [str(value)]


def _classify_actions(actions: list[str]) -> str:
    normalised = [a.lower() for a in actions]
    if not normalised or normalised == ["no-op"]:
        return "no-op"
    if "create" in normalised and "delete" in normalised:
        return "replace"
    if "create" in normalised:
        return "create"
    if "update" in normalised:
        return "update"
    if "delete" in normalised:
        return "delete"
    return "other"
