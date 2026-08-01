"""Structured identifier extraction for hypothesis-directed retrieval."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.ai.hypothesis_retrieval.versions import RETRIEVAL_IDENTIFIER_EXTRACTOR_VERSION
from app.domain.hypothesis_retrieval.models import HypothesisRetrievalContext
from app.domain.services.secret_masker import mask_secrets

_AWS_ACTION = re.compile(r"\b([a-z0-9-]{2,}):([A-Za-z][A-Za-z0-9]+)\b")
_AWS_ERROR = re.compile(r"\b([A-Z][A-Za-z0-9]*(?:Denied|Exception|Error|Failed))\b")
_ARN = re.compile(r"\barn:aws:[a-z0-9-]+:[a-z0-9-]*:\d{0,12}:[^\s,\"']+", re.IGNORECASE)
_TF_RESOURCE = re.compile(r"\b(aws_[a-z0-9_]+)\.([a-zA-Z0-9_-]+)\b")
_TF_TYPE = re.compile(r"\b(aws_[a-z0-9_]+)\b")
_PACKAGE = re.compile(r"\b([a-zA-Z0-9_.-]+)@([0-9]+\.[0-9][^ \t\n,]*)")
_EXIT_CODE = re.compile(r"\bexit(?:\s+code)?[=:\s]+(-?\d+)\b", re.IGNORECASE)
_EXCEPTION = re.compile(r"\b([A-Z][A-Za-z0-9_]+(?:Error|Exception))\b")
_SECRETISH = re.compile(
    r"(password|token|secret|private[_-]?key|api[_-]?key)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ExtractedIdentifiers:
    aws_actions: list[str] = field(default_factory=list)
    aws_error_codes: list[str] = field(default_factory=list)
    aws_arns: list[str] = field(default_factory=list)
    aws_services: list[str] = field(default_factory=list)
    terraform_resources: list[str] = field(default_factory=list)
    terraform_resource_types: list[str] = field(default_factory=list)
    gha_workflow_paths: list[str] = field(default_factory=list)
    package_coords: list[str] = field(default_factory=list)
    exception_names: list[str] = field(default_factory=list)
    exit_codes: list[str] = field(default_factory=list)
    changed_paths: list[str] = field(default_factory=list)
    commit_shas: list[str] = field(default_factory=list)
    all_identifiers: list[str] = field(default_factory=list)
    extractor_version: str = RETRIEVAL_IDENTIFIER_EXTRACTOR_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RetrievalIdentifierExtractor:
    """Extract safe structured identifiers; never persist secret values."""

    def __init__(self, *, max_identifiers: int = 32) -> None:
        self._max = max(1, max_identifiers)

    def extract(self, context: HypothesisRetrievalContext) -> ExtractedIdentifiers:
        blobs = [
            context.causal_claim,
            context.error_signature or "",
            context.title,
            " ".join(context.expected_observations),
            " ".join(context.falsifying_observations),
            " ".join(context.missing_evidence),
            " ".join(context.permission_actions),
            " ".join(context.resource_identifiers),
            " ".join(context.changed_files),
            context.workflow_path or "",
            context.combined_text_excerpt or "",
        ]
        text, _ = mask_secrets("\n".join(b for b in blobs if b))
        result = ExtractedIdentifiers()

        for match in _AWS_ACTION.finditer(text):
            action = f"{match.group(1)}:{match.group(2)}"
            _append_unique(result.aws_actions, action, self._max)
            _append_unique(result.aws_services, match.group(1), self._max)
        for match in _AWS_ERROR.finditer(text):
            _append_unique(result.aws_error_codes, match.group(1), self._max)
        for match in _ARN.finditer(text):
            arn = match.group(0)
            if _SECRETISH.search(arn):
                continue
            _append_unique(result.aws_arns, arn, self._max)
        for match in _TF_RESOURCE.finditer(text):
            _append_unique(
                result.terraform_resources,
                f"{match.group(1)}.{match.group(2)}",
                self._max,
            )
            _append_unique(result.terraform_resource_types, match.group(1), self._max)
        for match in _TF_TYPE.finditer(text):
            _append_unique(result.terraform_resource_types, match.group(1), self._max)
        for match in _PACKAGE.finditer(text):
            _append_unique(result.package_coords, f"{match.group(1)}@{match.group(2)}", self._max)
        for match in _EXCEPTION.finditer(text):
            _append_unique(result.exception_names, match.group(1), self._max)
        for match in _EXIT_CODE.finditer(text):
            _append_unique(result.exit_codes, match.group(1), self._max)

        if context.workflow_path and not _SECRETISH.search(context.workflow_path):
            _append_unique(result.gha_workflow_paths, context.workflow_path, self._max)
        for path in context.changed_files:
            if path and not _SECRETISH.search(path):
                _append_unique(result.changed_paths, path, self._max)
        if context.commit_sha and re.fullmatch(r"[0-9a-fA-F]{7,40}", context.commit_sha):
            _append_unique(result.commit_shas, context.commit_sha, self._max)
        for action in context.permission_actions:
            if action and not _SECRETISH.search(action):
                _append_unique(result.aws_actions, action, self._max)
        for rid in context.resource_identifiers:
            if rid and not _SECRETISH.search(rid):
                if rid.startswith("arn:"):
                    _append_unique(result.aws_arns, rid, self._max)
                else:
                    _append_unique(result.terraform_resources, rid, self._max)

        combined: list[str] = []
        for bucket in (
            result.aws_actions,
            result.aws_error_codes,
            result.aws_arns,
            result.terraform_resources,
            result.package_coords,
            result.exception_names,
            result.exit_codes,
            result.changed_paths,
            result.commit_shas,
            result.gha_workflow_paths,
        ):
            for item in bucket:
                _append_unique(combined, item, self._max)
        result.all_identifiers = combined
        return result


def _append_unique(target: list[str], value: str, limit: int) -> None:
    cleaned = value.strip()
    if not cleaned or cleaned in target or len(target) >= limit:
        return
    if (
        _SECRETISH.search(cleaned)
        and ":" not in cleaned
        and cleaned.lower() in {"password", "token", "secret", "apikey", "api_key"}
    ):
        return
    target.append(cleaned)
