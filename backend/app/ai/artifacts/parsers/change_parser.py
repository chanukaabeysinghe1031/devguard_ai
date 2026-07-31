"""Changed-files metadata structured parser."""

from __future__ import annotations

import json
from typing import Any

from app.ai.artifacts.parsers.base import StructuredArtifactParser
from app.domain.artifacts.enums import ArtifactKind, ParseStatus
from app.domain.artifacts.models import (
    DiagnosticMessage,
    EvidenceCandidate,
    GraphEntityPreview,
    SourceLocation,
    StructuredParseResult,
)

PARSER_VERSION = "1.0.0"


class ChangeParser(StructuredArtifactParser):
    name = "change_parser"
    version = PARSER_VERSION

    def supports(self, kind: ArtifactKind) -> bool:
        return kind in {
            ArtifactKind.CHANGED_FILES_METADATA,
            ArtifactKind.COMMIT_METADATA,
        }

    def parse(
        self,
        content: str,
        *,
        filename: str,
        kind: ArtifactKind,
    ) -> StructuredParseResult:
        entities: list[GraphEntityPreview] = []
        evidence: list[EvidenceCandidate] = []
        diagnostics: list[DiagnosticMessage] = []

        path_list, mode, errors, warnings = _extract_path_list(content)

        for index, item in enumerate(path_list):
            path = item["path"]
            entity_id = f"changed_file:{path}"
            entities.append(
                GraphEntityPreview(
                    id=entity_id,
                    type="CHANGED_FILE",
                    label=path,
                    location=SourceLocation(path=path),
                    metadata={
                        "status": item.get("status"),
                        "additions": item.get("additions"),
                        "deletions": item.get("deletions"),
                        "index": index,
                    },
                )
            )

        if entities:
            evidence.append(
                EvidenceCandidate(
                    kind="changed_files",
                    text="; ".join(e.label for e in entities[:20]),
                    location=SourceLocation(path=filename),
                    importance=0.55,
                    metadata={"count": len(entities)},
                )
            )

        if errors and not entities:
            status = ParseStatus.FAILED
            quality = 0.0
            diagnostics.append(
                DiagnosticMessage(
                    severity="error",
                    code="changed_files_parse_failed",
                    message=errors[0],
                )
            )
        elif not entities:
            status = ParseStatus.PARTIAL
            quality = 0.2
            warnings.append("No changed files extracted")
        else:
            status = ParseStatus.SUCCESS
            quality = min(1.0, 0.5 + 0.05 * len(entities))

        return StructuredParseResult(
            parser_name=self.name,
            parser_version=self.version,
            status=status,
            entities=entities,
            evidence_candidates=evidence,
            diagnostics=diagnostics,
            warnings=warnings,
            errors=errors,
            extraction_quality=quality,
            raw_summary={
                "filename": filename,
                "kind": kind.value,
                "mode": mode,
                "changed_file_count": len(entities),
                "paths": [e.label for e in entities],
            },
        )


def _extract_path_list(
    content: str,
) -> tuple[list[dict[str, Any]], str, list[str], list[str]]:
    stripped = content.strip()
    errors: list[str] = []
    warnings: list[str] = []
    if not stripped:
        return [], "empty", [], ["Empty changed-files content"]

    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            warnings.append(f"JSON parse failed, falling back to newline paths: {exc}")
            return _newline_paths(stripped), "newline_fallback", [], warnings

        items: list[dict[str, Any]] = []
        if isinstance(parsed, list):
            for entry in parsed:
                normalised = _normalise_entry(entry)
                if normalised:
                    items.append(normalised)
            return items, "json_list", errors, warnings

        if isinstance(parsed, dict):
            for key in ("files", "changed_files", "paths"):
                value = parsed.get(key)
                if isinstance(value, list):
                    for entry in value:
                        normalised = _normalise_entry(entry)
                        if normalised:
                            items.append(normalised)
                    return items, f"json_object.{key}", errors, warnings
            single = _normalise_entry(parsed)
            if single:
                return [single], "json_object.single", errors, warnings
            errors.append("JSON object did not contain changed file paths")
            return [], "json_object", errors, warnings

        errors.append(f"Unsupported JSON root type: {type(parsed).__name__}")
        return [], "json_other", errors, warnings

    return _newline_paths(stripped), "newline", errors, warnings


def _newline_paths(content: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in content.splitlines():
        path = line.strip()
        if not path or path.startswith("#"):
            continue
        parts = path.split(maxsplit=1)
        if len(parts) == 2 and parts[0] in {"A", "M", "D", "R", "C", "?", "U"}:
            items.append({"path": parts[1], "status": parts[0]})
        else:
            items.append({"path": path, "status": None})
    return items


def _normalise_entry(entry: Any) -> dict[str, Any] | None:
    if isinstance(entry, str) and entry.strip():
        return {"path": entry.strip(), "status": None}
    if isinstance(entry, dict):
        path = entry.get("filename") or entry.get("path") or entry.get("file")
        if isinstance(path, str) and path.strip():
            return {
                "path": path.strip(),
                "status": entry.get("status") or entry.get("change_type"),
                "additions": entry.get("additions"),
                "deletions": entry.get("deletions"),
            }
    return None
