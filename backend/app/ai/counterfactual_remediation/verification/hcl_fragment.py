"""Built-in HCL fragment structural verifier (parse-heuristics; no terraform binary)."""

from __future__ import annotations

import re
from typing import Any

from app.ai.counterfactual_remediation.verification._helpers import (
    artifact_type_str,
    is_terraform_family,
    proposed_content,
)
from app.ai.counterfactual_remediation.verification.base import BaseVerifier
from app.domain.counterfactual_remediation.verification_enums import VerifierResultStatus
from app.domain.counterfactual_remediation.verification_models import VerifierResult
from app.domain.counterfactual_remediation.verification_versions import HCL_FRAGMENT_VERIFIER_VERSION

_BLOCK_START = re.compile(
    r"^\s*(resource|data|module|variable|output|provider|terraform|locals)\s+",
    re.MULTILINE,
)
class HclFragmentVerifier(BaseVerifier):
    """Lightweight HCL fragment checks without requiring the terraform CLI."""

    name = "hcl_fragment"
    version = HCL_FRAGMENT_VERIFIER_VERSION

    def supports(self, candidate: Any) -> bool:
        artifact = artifact_type_str(candidate)
        if is_terraform_family(artifact):
            return True
        patch_format = str(getattr(candidate, "patch_format", "") or "").upper()
        return patch_format in {"HCL_FRAGMENT"}

    def execute(self, workspace: Any, candidate: Any) -> VerifierResult:
        content = proposed_content(candidate) or _read_first(workspace)
        if not content.strip():
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="no_hcl_content",
                findings=["empty_proposed_fragment"],
            )
        findings: list[str] = []
        if not _BLOCK_START.search(content):
            # Fragments may be attribute-only; warn rather than fail hard.
            findings.append("no_hcl_block_keyword_detected")
        opens = content.count("{")
        closes = content.count("}")
        if opens != closes:
            findings.append(f"unbalanced_braces:{opens}:{closes}")
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="hcl_unbalanced_braces",
                findings=findings,
            )
        # Rough quote balance for double quotes (ignoring escapes).
        if content.count('"') % 2 != 0:
            findings.append("unbalanced_double_quotes")
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="hcl_unbalanced_quotes",
                findings=findings,
            )
        status = (
            VerifierResultStatus.WARNING
            if findings
            else VerifierResultStatus.PASS
        )
        return self._result(
            status=status,
            candidate=candidate,
            message="hcl_fragment_ok",
            findings=findings,
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
