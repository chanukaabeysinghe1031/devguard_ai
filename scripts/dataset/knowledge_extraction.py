"""Phase 3 heuristic knowledge extraction from sanitised GitHub incidents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_HEADER = re.compile(r"(?m)^#{1,6}\s+(.+?)\s*$")
_CAUSE_LINE = re.compile(
    r"(?im)^(?:\s*[-*]?\s*)?(?:root\s*cause|cause|caused by|this happens because|"
    r"the issue (?:is|was)|reason)\s*[:\-–]\s*(.+)$"
)
_FIX_LINE = re.compile(
    r"(?im)^(?:\s*[-*]?\s*)?(?:fix|fixed by|workaround|resolution|solution|"
    r"resolved by|to fix|mitigation)\s*[:\-–]\s*(.+)$"
)

_SECTION_ALIASES: dict[str, str] = {
    "what happened?": "symptoms",
    "what happened": "symptoms",
    "description": "symptoms",
    "actual behavior": "symptoms",
    "actual behaviour": "symptoms",
    "observed behavior": "symptoms",
    "bug description": "symptoms",
    "summary": "symptoms",
    "expected behavior": "expected",
    "expected behaviour": "expected",
    "what did you expect to happen?": "expected",
    "what did you expect to happen": "expected",
    "steps to reproduce": "repro",
    "how can we reproduce it (as minimally and precisely as possible)?": "repro",
    "reproduction": "repro",
    "root cause": "root_cause",
    "cause": "root_cause",
    "analysis": "root_cause",
    "solution": "resolution",
    "workaround": "resolution",
    "fix": "resolution",
    "resolution": "resolution",
    "possible solution": "resolution",
    "additional context": "context",
    "additional information": "context",
}

_CATEGORY_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(?i)\b(accessdenied|access denied|not authorized|unauthorized|"
            r"iam\b|permission denied|explicit deny|AssumeRole)\b"
        ),
        "aws_permission_failure",
    ),
    (
        re.compile(r"(?i)\b(terraform|undeclared resource|provider plugin|state lock)\b"),
        "terraform_failure",
    ),
    (
        re.compile(
            r"(?i)\b(dockerfile|docker compose|imagepull|image pull|container|"
            r"COPY failed|buildx)\b"
        ),
        "docker_failure",
    ),
    (
        re.compile(
            r"(?i)\b(npm ERR|yarn\b|pip(3)?\b|ModuleNotFoundError|dependency conflict|"
            r"peer dep|package-lock)\b"
        ),
        "dependency_failure",
    ),
    (
        re.compile(r"(?i)\b(pytest|AssertionError|test failed|junit|surefire)\b"),
        "test_failure",
    ),
    (
        re.compile(r"(?i)\b(mvn\b|maven|gradle|compilation failed|build failed)\b"),
        "build_failure",
    ),
    (
        re.compile(
            r"(?i)\b(CrashLoopBackOff|ImagePullBackOff|kubelet|deployment failed|"
            r"rollout)\b"
        ),
        "deployment_failure",
    ),
    (
        re.compile(r"(?i)\b(timeout|timed out|connection refused|dns|ECONNREFUSED)\b"),
        "network_failure",
    ),
    (
        re.compile(r"(?i)\b(secret|credential|token leaked|insecure)\b"),
        "security_misconfiguration",
    ),
    (
        re.compile(r"(?i)\b(workflow|github actions|YAML|action\.yml|runner)\b"),
        "configuration_failure",
    ),
]


@dataclass(frozen=True)
class ExtractionResult:
    symptoms: str | None
    root_cause: str | None
    resolution: str | None
    failure_category: str
    confidence: str  # high | medium | low
    score: int
    sections_found: list[str]
    status: str  # curated | curation_candidate | rejected


def _clip(text: str | None, limit: int = 900) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not cleaned:
        return None
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def split_markdown_sections(body: str) -> dict[str, str]:
    matches = list(_HEADER.finditer(body))
    if not matches:
        return {"body": body.strip()} if body.strip() else {}

    sections: dict[str, str] = {}
    # Preface before first header
    preface = body[: matches[0].start()].strip()
    if preface:
        sections["preface"] = preface

    for idx, match in enumerate(matches):
        title = match.group(1).strip().lower()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        if not content:
            continue
        key = _SECTION_ALIASES.get(title, f"other:{title}")
        # Keep first non-empty for canonical keys; append for others.
        if key in sections and not key.startswith("other:"):
            sections[key] = sections[key] + "\n\n" + content
        else:
            sections[key] = content
    return sections


def refine_failure_category(
    *,
    current: str,
    title: str,
    description: str,
    technology: str,
) -> str:
    blob = f"{title}\n{description}"
    for pattern, code in _CATEGORY_RULES:
        if pattern.search(blob):
            return code
    # Technology fallbacks when no rule hit.
    tech_default = {
        "terraform": "terraform_failure",
        "docker": "docker_failure",
        "aws": "aws_permission_failure",
        "kubernetes": "deployment_failure",
        "java": "build_failure",
        "node": "dependency_failure",
        "npm": "dependency_failure",
        "python": "test_failure",
        "github_actions": "configuration_failure",
    }
    if current and current != "unknown_failure":
        return current
    return tech_default.get(technology, current or "unknown_failure")


def extract_knowledge(incident: dict[str, Any]) -> ExtractionResult:
    title = str(incident.get("title") or "").strip()
    description = str(incident.get("description") or "").strip()
    technology = str(incident.get("technology") or "other")
    current_category = str(incident.get("failure_category") or "unknown_failure")
    sections = split_markdown_sections(description)

    symptoms = sections.get("symptoms")
    if not symptoms and sections.get("preface"):
        symptoms = sections["preface"]
    if not symptoms and description:
        symptoms = description[:700]
    if not symptoms:
        symptoms = title

    root_cause = sections.get("root_cause")
    if not root_cause:
        match = _CAUSE_LINE.search(description)
        if match:
            root_cause = match.group(1).strip()

    # Expected vs actual gap can hint at cause when explicit cause missing.
    if not root_cause and sections.get("expected") and sections.get("symptoms"):
        root_cause = (
            "Expected behaviour differed from observed failure. "
            f"Expected: {_clip(sections['expected'], 220)}. "
            f"Observed: {_clip(sections['symptoms'], 220)}."
        )

    resolution = sections.get("resolution")
    if not resolution:
        match = _FIX_LINE.search(description)
        if match:
            resolution = match.group(1).strip()

    symptoms_c = _clip(symptoms, 900)
    root_cause_c = _clip(root_cause, 700)
    resolution_c = _clip(resolution, 700)

    category = refine_failure_category(
        current=current_category,
        title=title,
        description=description,
        technology=technology,
    )

    score = 0
    section_keys = sorted(k for k in sections if not k.startswith("other:"))
    if symptoms_c and len(symptoms_c) >= 40:
        score += 2
    if "symptoms" in sections:
        score += 1
    if root_cause_c and len(root_cause_c) >= 40:
        score += 3
    if resolution_c and len(resolution_c) >= 20:
        score += 3
    if incident.get("resolved"):
        score += 1
    if len(description) >= 200:
        score += 1

    if score >= 6 and symptoms_c and (root_cause_c or resolution_c):
        confidence, status = "high", "curated"
    elif score >= 4 and symptoms_c and len(description) >= 80:
        confidence, status = "medium", "curation_candidate"
    elif symptoms_c and len(f"{title}\n{description}") >= 40:
        confidence, status = "low", "curation_candidate"
    else:
        confidence, status = "low", "rejected"

    # Open issues should not auto-become curated knowledge.
    if str((incident.get("raw_metadata") or {}).get("phase2_source_pool") or "") == "open":
        if status == "curated":
            status = "curation_candidate"
        if confidence == "high":
            confidence = "medium"

    return ExtractionResult(
        symptoms=symptoms_c,
        root_cause=root_cause_c,
        resolution=resolution_c,
        failure_category=category,
        confidence=confidence,
        score=score,
        sections_found=section_keys,
        status=status,
    )


def to_knowledge_record(incident: dict[str, Any], extraction: ExtractionResult) -> dict[str, Any]:
    return {
        "knowledge_id": f"kn-{incident['incident_id']}",
        "incident_id": incident["incident_id"],
        "title": incident.get("title"),
        "symptoms": extraction.symptoms,
        "root_cause": extraction.root_cause,
        "resolution": extraction.resolution,
        "technology": incident.get("technology"),
        "failure_category": extraction.failure_category,
        "repository": incident.get("repository"),
        "issue_url": incident.get("issue_url"),
        "resolved": incident.get("resolved"),
        "extraction_confidence": extraction.confidence,
        "extraction_score": extraction.score,
        "extraction_method": "heuristic_v1",
        "sections_found": extraction.sections_found,
        "source_pool": (incident.get("raw_metadata") or {}).get("phase2_source_pool"),
    }
