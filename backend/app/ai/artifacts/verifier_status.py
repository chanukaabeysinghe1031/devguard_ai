"""Optional verifier tool availability (Phase 6A.1 stub — execution in 6A.7)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from shutil import which


class VerifierState(StrEnum):
    """Never invent PASS. Missing tools are UNAVAILABLE."""

    UNAVAILABLE = "unavailable"
    AVAILABLE = "available"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class VerifierToolStatus:
    name: str
    state: VerifierState
    binary: str | None = None
    detail: str | None = None


_KNOWN_VERIFIERS: tuple[tuple[str, str], ...] = (
    ("actionlint", "actionlint"),
    ("terraform", "terraform"),
    ("checkov", "checkov"),
)


def probe_verifier_tools(*, enabled: bool = False) -> list[VerifierToolStatus]:
    """Report install presence only. Does not execute verifiers."""
    if not enabled:
        return [
            VerifierToolStatus(
                name=name,
                state=VerifierState.DISABLED,
                binary=binary,
                detail="Verifier execution belongs to Phase 6A.7; disabled in 6A.1",
            )
            for name, binary in _KNOWN_VERIFIERS
        ]
    statuses: list[VerifierToolStatus] = []
    for name, binary in _KNOWN_VERIFIERS:
        path = which(binary)
        if path:
            statuses.append(
                VerifierToolStatus(
                    name=name,
                    state=VerifierState.AVAILABLE,
                    binary=path,
                    detail="Binary present; execution not invoked in Phase 6A.1",
                )
            )
        else:
            statuses.append(
                VerifierToolStatus(
                    name=name,
                    state=VerifierState.UNAVAILABLE,
                    binary=binary,
                    detail="Binary not installed; never record fake PASS",
                )
            )
    return statuses
