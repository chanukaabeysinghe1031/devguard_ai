"""Lightweight metadata extractors (parsing interfaces only — no AI)."""

from __future__ import annotations

import json
import re
from typing import Any

import yaml

from app.domain.enums import FileType
from app.domain.interfaces.parsers import ArtifactParser


class LogMetadataExtractor(ArtifactParser):
    def supports(self, file_type: FileType) -> bool:
        return file_type == FileType.LOG

    def extract_metadata(self, *, content: str, original_filename: str) -> dict[str, Any]:
        lines = content.splitlines()
        error_lines = sum(1 for line in lines if re.search(r"(?i)\berror\b|\bfailed\b", line))
        return {
            "parser": "log",
            "original_filename": original_filename,
            "line_count": len(lines),
            "char_count": len(content),
            "error_keyword_lines": error_lines,
        }


class YamlMetadataExtractor(ArtifactParser):
    def supports(self, file_type: FileType) -> bool:
        return file_type == FileType.WORKFLOW_YAML

    def extract_metadata(self, *, content: str, original_filename: str) -> dict[str, Any]:
        parsed = yaml.safe_load(content)
        jobs = []
        name = None
        if isinstance(parsed, dict):
            name = parsed.get("name")
            raw_jobs = parsed.get("jobs")
            if isinstance(raw_jobs, dict):
                jobs = list(raw_jobs.keys())
        return {
            "parser": "workflow_yaml",
            "original_filename": original_filename,
            "workflow_name": name,
            "job_count": len(jobs),
            "jobs": jobs[:50],
            "line_count": len(content.splitlines()),
        }


class JsonMetadataExtractor(ArtifactParser):
    def supports(self, file_type: FileType) -> bool:
        return file_type == FileType.JSON

    def extract_metadata(self, *, content: str, original_filename: str) -> dict[str, Any]:
        parsed = json.loads(content)
        return {
            "parser": "json",
            "original_filename": original_filename,
            "root_type": type(parsed).__name__,
            "line_count": len(content.splitlines()),
        }


class TerraformMetadataExtractor(ArtifactParser):
    def supports(self, file_type: FileType) -> bool:
        return file_type == FileType.TERRAFORM

    def extract_metadata(self, *, content: str, original_filename: str) -> dict[str, Any]:
        resources = re.findall(
            r'resource\s+"([^"]+)"\s+"([^"]+)"',
            content,
        )
        modules = re.findall(r'module\s+"([^"]+)"', content)
        return {
            "parser": "terraform",
            "original_filename": original_filename,
            "resource_count": len(resources),
            "resources": [{"type": t, "name": n} for t, n in resources[:50]],
            "module_count": len(modules),
            "line_count": len(content.splitlines()),
        }


def get_parser_for(file_type: FileType) -> ArtifactParser | None:
    parsers: list[ArtifactParser] = [
        LogMetadataExtractor(),
        YamlMetadataExtractor(),
        JsonMetadataExtractor(),
        TerraformMetadataExtractor(),
    ]
    for parser in parsers:
        if parser.supports(file_type):
            return parser
    return None


def validate_syntax(file_type: FileType, content: str) -> None:
    """Raise ValueError when content fails basic syntax checks."""
    if file_type == FileType.JSON:
        json.loads(content)
        return
    if file_type == FileType.WORKFLOW_YAML:
        yaml.safe_load(content)
        return
    # Terraform / logs: no hard syntax rejection beyond UTF-8 text.
