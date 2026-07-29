"""Deterministic diagnostic signal extraction (no LLM)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ai.orchestration.analysis_context import AnalysisContext
from app.ai.rag.stack_trace import stack_trace_fingerprint

_ERROR_CODE = re.compile(
    r"\b(AccessDenied|UnauthorizedOperation|NoCredentialProviders|"
    r"ExpiredToken|ERESOLVE|ECONNREFUSED|ETIMEDOUT|ErrorLock|"
    r"StateLocked|ImageNotFound|ManifestUnknown|"
    r"[A-Z][A-Za-z]+Exception|[A-Z][A-Za-z]+Error)\b"
)
_AWS_SERVICE = re.compile(
    r"\b(ecs|iam|s3|ec2|lambda|sts|cloudformation|eks|rds|dynamodb)"
    r"(?:[:.][A-Za-z0-9]+)?\b",
    re.I,
)
_TF_RESOURCE = re.compile(r"\b(resource|data)\s+\"([a-z0-9_]+)\"\s+\"([a-z0-9_-]+)\"")
_DOCKER_INSTR = re.compile(
    r"^\s*(FROM|RUN|COPY|ADD|CMD|ENTRYPOINT|ENV|EXPOSE|WORKDIR)\b",
    re.I | re.M,
)
_COMMAND = re.compile(
    r"\b((?:npm|yarn|pnpm|pip|pip3|mvn|gradle|terraform|docker|kubectl|"
    r"aws|git|pytest|python|node)\s+[a-z0-9_.:/-]+)",
    re.I,
)
_STAGE = re.compile(
    r"\b(build|test|deploy|plan|apply|lint|install|checkout|setup|"
    r"publish|release|validate)\b",
    re.I,
)
_TECHNOLOGIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "GitHub Actions",
        re.compile(
            r"github[_ ]?actions"
            r"|::set-output"
            r"|actions/"
            r"|\.github/workflows"
            r"|workflow_dispatch"
            r"|GITHUB_ACTIONS\s*=\s*true"
            r"|GITHUB_RUN_ID"
            r"|github-hosted runner"
            r"|self-hosted runner"
            r"|runs-on:"
            r"|actions-runner"
            r"|actions\.runner",
            re.I,
        ),
    ),
    ("Jenkins", re.compile(r"\bjenkins\b", re.I)),
    ("Docker", re.compile(r"\bdocker\b|dockerfile", re.I)),
    ("Terraform", re.compile(r"\bterraform\b|\.tf\b", re.I)),
    ("Kubernetes", re.compile(r"\bkubernetes\b|\bkubectl\b|\bk8s\b", re.I)),
    ("AWS", re.compile(r"\baws\b|amazonaws\.com|AccessDenied", re.I)),
    ("Java", re.compile(r"\bjava\b|\.java\b|Exception in thread", re.I)),
    ("Python", re.compile(r"\bpython\b|\.py\b|Traceback \(most recent", re.I)),
    ("Node.js", re.compile(r"\bnode(?:\.js)?\b|npm ERR!", re.I)),
    ("Maven", re.compile(r"\bmaven\b|\bmvn\b", re.I)),
    ("Gradle", re.compile(r"\bgradle\b", re.I)),
    ("npm", re.compile(r"\bnpm\b|package-lock\.json", re.I)),
    ("pip", re.compile(r"\bpip(?:3)?\b|requirements\.txt", re.I)),
)
_GENERIC_FALSE_POSITIVES = frozenset(
    {"error", "failed", "failure", "exception", "warning", "info", "debug"}
)


@dataclass
class DiagnosticSignals:
    failure_category: str | None = None
    pipeline_stage: str | None = None
    technologies: list[str] = field(default_factory=list)
    error_codes: list[str] = field(default_factory=list)
    exception_names: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    resource_types: list[str] = field(default_factory=list)
    file_types: list[str] = field(default_factory=list)
    aws_services: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    stack_trace_fingerprint: str | None = None


class DiagnosticSignalExtractor:
    """Extract structured diagnostic signals without LLM calls."""

    def extract(self, context: AnalysisContext) -> DiagnosticSignals:
        text = context.combined_text or ""
        category = context.classifications[0].category_code if context.classifications else None
        signals = DiagnosticSignals(failure_category=category)

        # Prefer existing Module 6/8 signals when present.
        existing = context.signals or {}
        if existing.get("provider"):
            provider = str(existing["provider"]).lower()
            mapping = {
                "aws": "AWS",
                "docker": "Docker",
                "terraform": "Terraform",
                "npm": "npm",
            }
            if provider in mapping:
                signals.technologies.append(mapping[provider])

        signals.file_types = sorted(
            {f.file_type.value for f in context.files}
            | {str(t) for t in (existing.get("file_types") or [])}
        )

        signals.error_codes = _unique(
            [
                m.group(1)
                for m in _ERROR_CODE.finditer(text)
                if m.group(1).lower() not in _GENERIC_FALSE_POSITIVES
            ]
        )
        signals.exception_names = [
            code
            for code in signals.error_codes
            if code.endswith(("Exception", "Error")) and code not in {"Error"}
        ]
        signals.aws_services = _unique([m.group(1).lower() for m in _AWS_SERVICE.finditer(text)])
        signals.resource_types = _unique([f"{m.group(2)}" for m in _TF_RESOURCE.finditer(text)])
        signals.commands = _unique([m.group(1).strip() for m in _COMMAND.finditer(text)])[:12]
        stages = [m.group(1).lower() for m in _STAGE.finditer(text)]
        signals.pipeline_stage = stages[0] if stages else None

        for name, pattern in _TECHNOLOGIES:
            if pattern.search(text) and name not in signals.technologies:
                signals.technologies.append(name)

        docker_instr = _unique([m.group(1).upper() for m in _DOCKER_INSTR.finditer(text)])
        if docker_instr and "Docker" not in signals.technologies:
            signals.technologies.append("Docker")
        if docker_instr:
            signals.keywords.extend(docker_instr)

        for item in context.evidence[:8]:
            excerpt = (item.normalized_excerpt or "")[:120]
            if excerpt:
                signals.keywords.append(excerpt.split()[0] if excerpt.split() else excerpt)

        signals.keywords = _unique(
            [
                k
                for k in signals.keywords
                if k.lower() not in _GENERIC_FALSE_POSITIVES and len(k) >= 3
            ]
        )[:20]
        signals.stack_trace_fingerprint = stack_trace_fingerprint(text)

        # Merge into context.signals for downstream consumers.
        context.signals = {
            **existing,
            "failure_category": signals.failure_category,
            "pipeline_stage": signals.pipeline_stage,
            "technologies": list(signals.technologies),
            "error_codes": list(signals.error_codes),
            "exception_names": list(signals.exception_names),
            "commands": list(signals.commands),
            "resource_types": list(signals.resource_types),
            "aws_services": list(signals.aws_services),
            "stack_trace_fingerprint": signals.stack_trace_fingerprint,
        }
        return signals


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out
