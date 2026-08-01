"""AWS AccessDenied text and IAM policy JSON structured parser."""

from __future__ import annotations

import json
import re
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

_ACCESS_DENIED_RE = re.compile(
    r"(?i)(?P<line>.*(?:AccessDenied|not authorized to perform|ExplicitDeny).*)"
)
_ACTION_RE = re.compile(r"(?i)(?:perform|action)[:\s]+`?(?P<action>[a-z0-9]+:[A-Za-z0-9*]+)`?")


class AwsPolicyParser(StructuredArtifactParser):
    name = "aws_policy_parser"
    version = PARSER_VERSION

    def supports(self, kind: ArtifactKind) -> bool:
        return kind in {
            ArtifactKind.IAM_POLICY_JSON,
            ArtifactKind.AWS_ERROR_METADATA,
        }

    def parse(
        self,
        content: str,
        *,
        filename: str,
        kind: ArtifactKind,
    ) -> StructuredParseResult:
        stripped = content.strip()
        if not stripped:
            return StructuredParseResult(
                parser_name=self.name,
                parser_version=self.version,
                status=ParseStatus.PARTIAL,
                warnings=["Empty AWS/IAM content"],
                extraction_quality=0.1,
                raw_summary={"filename": filename, "mode": "empty"},
            )

        # Prefer JSON policy when content looks like JSON
        if stripped.startswith("{") or stripped.startswith("["):
            return self._parse_policy_json(stripped, filename=filename, kind=kind)
        return self._parse_error_text(stripped, filename=filename, kind=kind)

    def _parse_error_text(
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

        matches = list(_ACCESS_DENIED_RE.finditer(content))
        for index, match in enumerate(matches, start=1):
            line = match.group("line").strip()
            line_no = content[: match.start()].count("\n") + 1
            action_match = _ACTION_RE.search(line)
            action = action_match.group("action") if action_match else None
            entity_id = f"aws_error:{index}"
            entities.append(
                GraphEntityPreview(
                    id=entity_id,
                    type="AWS_ERROR",
                    label=line[:160],
                    location=SourceLocation(
                        path=filename,
                        line_start=line_no,
                        line_end=line_no,
                    ),
                    metadata={"action": action, "error_code": "AccessDenied"},
                )
            )
            evidence.append(
                EvidenceCandidate(
                    kind="aws_access_denied",
                    text=line[:1000],
                    location=SourceLocation(
                        path=filename,
                        line_start=line_no,
                        line_end=line_no,
                    ),
                    importance=0.95,
                    metadata={"action": action},
                )
            )
            if action:
                action_id = f"aws_action:{action}"
                if not any(e.id == action_id for e in entities):
                    entities.append(
                        GraphEntityPreview(
                            id=action_id,
                            type="AWS_ACTION",
                            label=action,
                            location=SourceLocation(path=filename),
                            metadata={"action": action},
                        )
                    )
                relationships.append(
                    GraphRelationshipPreview(
                        source_id=entity_id,
                        target_id=action_id,
                        type="REFERENCES",
                        confidence=0.9,
                        explanation=f"AccessDenied references {action}",
                        deterministic=True,
                    )
                )

        if not matches:
            diagnostics.append(
                DiagnosticMessage(
                    severity="warning",
                    code="no_access_denied",
                    message="No AccessDenied pattern detected in text",
                )
            )
            status = ParseStatus.PARTIAL
            quality = 0.3
        else:
            status = ParseStatus.SUCCESS
            quality = min(1.0, 0.5 + 0.1 * len(matches))
            diagnostics.append(
                DiagnosticMessage(
                    severity="error",
                    code="access_denied_detected",
                    message=f"Detected {len(matches)} AccessDenied-related line(s)",
                )
            )

        return StructuredParseResult(
            parser_name=self.name,
            parser_version=self.version,
            status=status,
            entities=entities,
            relationships=relationships,
            diagnostics=diagnostics,
            evidence_candidates=evidence,
            extraction_quality=quality,
            raw_summary={
                "filename": filename,
                "kind": kind.value,
                "mode": "error_text",
                "access_denied_count": len(matches),
            },
        )

    def _parse_policy_json(
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
        errors: list[str] = []
        warnings: list[str] = []

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            # Fall back to text mode if JSON is invalid but AccessDenied present
            if _ACCESS_DENIED_RE.search(content):
                return self._parse_error_text(content, filename=filename, kind=kind)
            errors.append(f"Invalid IAM policy JSON: {exc}")
            diagnostics.append(
                DiagnosticMessage(
                    severity="error",
                    code="invalid_iam_json",
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
                raw_summary={"filename": filename, "mode": "policy_json"},
            )

        policy_doc = _unwrap_policy(parsed)
        if policy_doc is None:
            warnings.append("No Statement block found in IAM JSON")
            # Still record AccessDenied if embedded
            if _ACCESS_DENIED_RE.search(content):
                return self._parse_error_text(content, filename=filename, kind=kind)
            return StructuredParseResult(
                parser_name=self.name,
                parser_version=self.version,
                status=ParseStatus.PARTIAL,
                warnings=warnings,
                extraction_quality=0.2,
                raw_summary={"filename": filename, "mode": "policy_json"},
            )

        policy_id = f"iam_policy:{filename}"
        entities.append(
            GraphEntityPreview(
                id=policy_id,
                type="IAM_POLICY",
                label=filename,
                location=SourceLocation(path=filename),
                metadata={
                    "Version": policy_doc.get("Version"),
                    "Id": policy_doc.get("Id"),
                },
            )
        )

        statements = policy_doc.get("Statement")
        statement_list = (
            statements
            if isinstance(statements, list)
            else ([statements] if isinstance(statements, dict) else [])
        )

        for index, statement in enumerate(statement_list):
            if not isinstance(statement, dict):
                continue
            sid = str(statement.get("Sid") or f"statement-{index}")
            stmt_id = f"policy_statement:{sid}"
            effect = statement.get("Effect")
            actions = _as_list(statement.get("Action"))
            resources = _as_list(statement.get("Resource"))
            condition = statement.get("Condition")
            entities.append(
                GraphEntityPreview(
                    id=stmt_id,
                    type="POLICY_STATEMENT",
                    label=sid,
                    location=SourceLocation(path=filename),
                    metadata={
                        "Effect": effect,
                        "Action": actions,
                        "Resource": resources,
                        "Condition": condition,
                    },
                )
            )
            relationships.append(
                GraphRelationshipPreview(
                    source_id=policy_id,
                    target_id=stmt_id,
                    type="CONTAINS",
                    confidence=1.0,
                    explanation=f"Policy contains statement {sid}",
                    deterministic=True,
                )
            )
            if str(effect).lower() == "deny":
                evidence.append(
                    EvidenceCandidate(
                        kind="iam_deny_statement",
                        text=json.dumps(
                            {
                                "Sid": sid,
                                "Effect": effect,
                                "Action": actions,
                                "Resource": resources,
                            },
                            sort_keys=True,
                        )[:1000],
                        location=SourceLocation(path=filename),
                        importance=0.85,
                        metadata={"sid": sid},
                    )
                )

        status = ParseStatus.SUCCESS if statement_list else ParseStatus.PARTIAL
        quality = 0.9 if statement_list else 0.3

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
                "mode": "policy_json",
                "statement_count": len(statement_list),
                "version": policy_doc.get("Version"),
            },
        )


def _unwrap_policy(parsed: Any) -> dict[str, Any] | None:
    if isinstance(parsed, dict):
        if "Statement" in parsed:
            return parsed
        # Common wrappers: PolicyDocument / policy_document / Document
        for key in ("PolicyDocument", "policy_document", "Document", "policy"):
            nested = parsed.get(key)
            if isinstance(nested, dict) and "Statement" in nested:
                return nested
            if isinstance(nested, str):
                try:
                    inner = json.loads(nested)
                except json.JSONDecodeError:
                    continue
                if isinstance(inner, dict) and "Statement" in inner:
                    return inner
    return None


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]
