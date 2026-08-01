"""Safe subprocess runner for verifier tools (never shell=True)."""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.ai.counterfactual_remediation.verification._helpers import redact_and_truncate

logger = logging.getLogger(__name__)

# Hard denylist — never invoke mutation / cloud / deploy tooling via this runner.
_FORBIDDEN_BINARIES = frozenset(
    {
        "aws",
        "kubectl",
        "helm",
        "docker",
        "git",
        "gh",
        "pulumi",
        "ansible-playbook",
    }
)


@dataclass(slots=True)
class SubprocessResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_ms: float = 0.0
    argv: list[str] | None = None
    unavailable: bool = False
    message: str = ""
    tool_path: str | None = None


def run_tool(
    argv: Sequence[str],
    *,
    cwd: str | Path,
    timeout: float = 60.0,
    max_stdout_chars: int = 20_000,
    env: dict[str, str] | None = None,
) -> SubprocessResult:
    """
    Execute a fixed argv list with shell=False, timeout, and redacted output.

    Never uses shell=True. Never invents PASS. Callers interpret returncode.
    """
    if not argv:
        raise ValueError("argv must be non-empty")
    binary = Path(str(argv[0])).name.lower()
    if binary in _FORBIDDEN_BINARIES:
        raise ValueError(f"forbidden verifier binary: {binary}")
    lowered_args = [str(a).lower() for a in argv[1:]]
    # Block terraform apply / destroy and similar mutation verbs when present as
    # a top-level subcommand-like token (not path fragments).
    if binary == "terraform" and any(tok in {"apply", "destroy", "import"} for tok in lowered_args):
        raise ValueError("terraform apply/destroy/import is forbidden in verifier runner")
    if binary == "git":
        raise ValueError("git is forbidden in verifier runner")

    workdir = str(Path(cwd).resolve())
    started = time.perf_counter()
    try:
        completed = subprocess.run(  # noqa: S603 — fixed argv, shell=False
            [str(a) for a in argv],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=max(0.1, float(timeout)),
            shell=False,
            check=False,
            env=env,
        )
        duration_ms = (time.perf_counter() - started) * 1000.0
        stdout = redact_and_truncate(completed.stdout, max_chars=max_stdout_chars)
        stderr = redact_and_truncate(completed.stderr, max_chars=max_stdout_chars)
        return SubprocessResult(
            returncode=int(completed.returncode),
            stdout=stdout,
            stderr=stderr,
            timed_out=False,
            duration_ms=duration_ms,
            argv=[str(a) for a in argv],
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = (time.perf_counter() - started) * 1000.0
        stdout = redact_and_truncate(
            exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else exc.stdout,
            max_chars=max_stdout_chars,
        )
        stderr = redact_and_truncate(
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else exc.stderr,
            max_chars=max_stdout_chars,
        )
        logger.warning("verifier tool timed out: %s", argv[0])
        return SubprocessResult(
            returncode=-1,
            stdout=stdout,
            stderr=stderr or "timeout",
            timed_out=True,
            duration_ms=duration_ms,
            argv=[str(a) for a in argv],
        )
    except FileNotFoundError:
        duration_ms = (time.perf_counter() - started) * 1000.0
        return SubprocessResult(
            returncode=127,
            stdout="",
            stderr=f"binary_not_found:{argv[0]}",
            timed_out=False,
            duration_ms=duration_ms,
            argv=[str(a) for a in argv],
        )
