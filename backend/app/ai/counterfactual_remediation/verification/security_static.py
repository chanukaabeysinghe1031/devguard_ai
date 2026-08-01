"""Built-in static security heuristics on proposed counterfactual content."""

from __future__ import annotations

import re
from typing import Any

from app.ai.counterfactual_remediation.safety import contains_secret_material
from app.ai.counterfactual_remediation.verification._helpers import (
    flag,
    proposed_content,
)
from app.ai.counterfactual_remediation.verification.base import BaseVerifier
from app.domain.counterfactual_remediation.verification_enums import VerifierResultStatus
from app.domain.counterfactual_remediation.verification_models import VerifierResult
from app.domain.counterfactual_remediation.verification_versions import (
    SECURITY_STATIC_VERIFIER_VERSION,
)

_WILDCARD_ACTION = re.compile(
    r'(?i)["\']?(?:Action|actions?)["\']?\s*[:=]\s*\[?\s*["\']\*["\']',
)
_WILDCARD_RESOURCE = re.compile(
    r'(?i)["\']?(?:Resource|resources?)["\']?\s*[:=]\s*\[?\s*["\']\*["\']',
)
_PUBLIC_HINTS = re.compile(
    r"(?i)\b(acl\s*=\s*[\"']?public|public-read|0\.0\.0\.0/0|::/0|"
    r"cidr_blocks\s*=\s*\[[^\]]*[\"']0\.0\.0\.0/0)\b",
)
_TLS_DISABLE = re.compile(
    r"(?i)\b(insecure_skip_verify\s*[:=]\s*true|"
    r"rejectunauthorized\s*[:=]\s*false|"
    r"ssl\s*[:=]\s*false|"
    r"encrypt\s*[:=]\s*false|"
    r"encryption\s*[:=]\s*false|"
    r"disable.?ssl|tls.?disable)\b",
)


class SecurityStaticVerifier(BaseVerifier):
    """
    Heuristic security checks on proposed content.

    Flag-gated via SECURITY_VERIFIER_ENABLED. FAIL blocks VERIFIED consensus.
    """

    name = "security_static"
    version = SECURITY_STATIC_VERIFIER_VERSION

    def __init__(self, *, enabled: bool = False) -> None:
        self._enabled = enabled

    @classmethod
    def from_settings(cls, settings: Any) -> SecurityStaticVerifier:
        return cls(enabled=flag(settings, "security_verifier_enabled", False))

    def supports(self, candidate: Any) -> bool:
        return self._enabled

    def is_available(self) -> bool:
        return self._enabled

    def execute(self, workspace: Any, candidate: Any) -> VerifierResult:
        if not self._enabled:
            return self._result(
                status=VerifierResultStatus.UNAVAILABLE,
                candidate=candidate,
                message="security_verifier_disabled",
            )
        content = proposed_content(candidate) or _read_first(workspace)
        if not content.strip():
            return self._result(
                status=VerifierResultStatus.WARNING,
                candidate=candidate,
                message="no_content_for_security_scan",
            )
        findings: list[str] = []
        if contains_secret_material(content):
            findings.append("secret_material_detected")
        if _WILDCARD_ACTION.search(content):
            findings.append("wildcard_action")
        if _WILDCARD_RESOURCE.search(content):
            findings.append("wildcard_resource")
        if _PUBLIC_HINTS.search(content):
            findings.append("public_exposure_hint")
        if _TLS_DISABLE.search(content):
            findings.append("encryption_or_tls_disabled")

        if findings:
            return self._result(
                status=VerifierResultStatus.FAIL,
                candidate=candidate,
                message="security_static_failed",
                findings=findings,
            )
        return self._result(
            status=VerifierResultStatus.PASS,
            candidate=candidate,
            message="security_static_ok",
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
