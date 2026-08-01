"""Built-in dependency manifest parse verifier."""

from __future__ import annotations

import json
import re
from typing import Any

from app.ai.counterfactual_remediation.verification._helpers import (
    artifact_type_str,
    is_dependency_family,
    proposed_content,
)
from app.ai.counterfactual_remediation.verification.base import BaseVerifier
from app.domain.counterfactual_remediation.verification_enums import VerifierResultStatus
from app.domain.counterfactual_remediation.verification_models import VerifierResult
from app.domain.counterfactual_remediation.verification_versions import (
    DEPENDENCY_MANIFEST_VERIFIER_VERSION,
)

_REQ_LINE = re.compile(
    r"^\s*([A-Za-z0-9_.\-]+)(\s*[<>=!~]=?\s*[^\s;]+)?\s*(#.*)?$",
)


class DependencyManifestVerifier(BaseVerifier):
    """Parse JSON / TOML / requirements-ish dependency manifests."""

    name = "dependency_manifest"
    version = DEPENDENCY_MANIFEST_VERIFIER_VERSION

    def supports(self, candidate: Any) -> bool:
        artifact = artifact_type_str(candidate)
        if is_dependency_family(artifact):
            return True
        patch_format = str(getattr(candidate, "patch_format", "") or "").upper()
        return patch_format == "DEPENDENCY_MANIFEST"

    def execute(self, workspace: Any, candidate: Any) -> VerifierResult:
        content = proposed_content(candidate) or _read_first(workspace)
        if not content.strip():
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="no_manifest_content",
                findings=["empty_proposed_fragment"],
            )
        stripped = content.lstrip()
        # JSON (package.json, etc.)
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                json.loads(content)
            except json.JSONDecodeError as exc:
                return self._result(
                    status=VerifierResultStatus.FAIL,
                    candidate=candidate,
                    message="manifest_json_invalid",
                    findings=[f"json_error:{exc.msg}"],
                )
            return self._result(
                status=VerifierResultStatus.PASS,
                candidate=candidate,
                message="manifest_json_ok",
            )

        # TOML
        if _looks_like_toml(stripped):
            try:
                import tomllib
            except ImportError:  # pragma: no cover
                return self._result(
                    status=VerifierResultStatus.UNAVAILABLE,
                    candidate=candidate,
                    message="tomllib_unavailable",
                )
            try:
                tomllib.loads(content)
            except Exception as exc:  # noqa: BLE001 — surface parse failure honestly
                return self._result(
                    status=VerifierResultStatus.FAIL,
                    candidate=candidate,
                    message="manifest_toml_invalid",
                    findings=[f"toml_error:{type(exc).__name__}"],
                )
            return self._result(
                status=VerifierResultStatus.PASS,
                candidate=candidate,
                message="manifest_toml_ok",
            )

        # requirements.txt-ish
        findings: list[str] = []
        valid_lines = 0
        for line_no, line in enumerate(content.splitlines(), start=1):
            text = line.strip()
            if not text or text.startswith("#") or text.startswith("-"):
                continue
            if _REQ_LINE.match(text):
                valid_lines += 1
            else:
                findings.append(f"unparsed_requirement_line:{line_no}")
        if valid_lines == 0 and findings:
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="manifest_unrecognized",
                findings=findings,
            )
        if findings:
            return self._result(
                status=VerifierResultStatus.WARNING,
                candidate=candidate,
                message="manifest_partial",
                findings=findings,
                metadata={"valid_lines": valid_lines},
            )
        return self._result(
            status=VerifierResultStatus.PASS,
            candidate=candidate,
            message="manifest_ok",
            metadata={"valid_lines": valid_lines},
        )


def _looks_like_toml(text: str) -> bool:
    return bool(
        re.search(r"^\s*\[[^\]]+\]", text, re.MULTILINE)
        or re.search(r"^\s*[A-Za-z0-9_.\-]+\s*=\s*", text, re.MULTILINE)
    )


def _read_first(workspace: Any) -> str:
    root = getattr(workspace, "root", None)
    files = getattr(workspace, "files_written", None) or []
    if root is None or not files:
        return ""
    try:
        return (root / files[0]).read_text(encoding="utf-8")
    except OSError:
        return ""
