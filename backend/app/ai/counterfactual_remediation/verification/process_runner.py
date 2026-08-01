"""Bounded subprocess runner — thin re-export of subprocess_runner."""

from __future__ import annotations

from shutil import which

from app.ai.counterfactual_remediation.verification.subprocess_runner import (
    SubprocessResult,
    run_tool,
)

# Backward-compatible names used by draft external adapters.
ProcessOutcome = SubprocessResult
resolve_binary = which


def run_argv(
    argv,
    *,
    cwd,
    timeout_seconds: float = 60.0,
    max_stdout_chars: int = 20_000,
    env=None,
):
    result = run_tool(
        argv,
        cwd=cwd,
        timeout=timeout_seconds,
        max_stdout_chars=max_stdout_chars,
        env=env,
    )
    unavailable = result.returncode == 127 or "binary_not_found" in (result.stderr or "")
    message = "timeout" if result.timed_out else ("" if result.returncode == 0 else "failed")
    return SubprocessResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        timed_out=result.timed_out,
        duration_ms=result.duration_ms,
        argv=result.argv,
        unavailable=unavailable,
        message=message,
        tool_path=str(argv[0]) if argv else None,
    )


__all__ = [
    "ProcessOutcome",
    "SubprocessResult",
    "resolve_binary",
    "run_argv",
    "run_tool",
]
