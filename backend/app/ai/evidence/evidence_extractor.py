"""Evidence extraction from normalized analysis inputs."""

from __future__ import annotations

import re

from app.ai.classification.rule_based_classifier import RULES
from app.ai.orchestration.analysis_context import AnalysisContext, EvidenceCandidate
from app.domain.enums import EvidenceType
from app.domain.services.secret_masker import mask_secrets

_STACK_TRACE = re.compile(
    r"(?m)^(?:Traceback \(most recent call last\):|\s+at |\s+File \".+\", line \d+).*"
)
_BEFORE = 5
_AFTER = 10


class EvidenceExtractor:
    def extract(self, context: AnalysisContext) -> list[EvidenceCandidate]:
        evidence: list[EvidenceCandidate] = []
        primary = context.classifications[0].category_code if context.classifications else None

        for loaded in context.files:
            lines = loaded.content.splitlines()
            evidence.extend(self._from_rules(loaded, lines, primary))
            evidence.extend(self._from_stack_traces(loaded, lines))

        # Deduplicate by excerpt fingerprint; keep highest importance.
        unique: dict[str, EvidenceCandidate] = {}
        for item in evidence:
            key = f"{item.uploaded_file_id}:{item.line_start}:{item.normalized_excerpt[:120]}"
            existing = unique.get(key)
            if existing is None or item.importance_score > existing.importance_score:
                unique[key] = item

        ranked = sorted(unique.values(), key=lambda e: e.importance_score, reverse=True)[:20]
        context.evidence = ranked
        return ranked

    def _from_rules(
        self,
        loaded,
        lines: list[str],
        primary: str | None,
    ) -> list[EvidenceCandidate]:
        results: list[EvidenceCandidate] = []
        for idx, line in enumerate(lines):
            for rule in RULES:
                if not rule.pattern.search(line):
                    continue
                start = max(0, idx - _BEFORE)
                end = min(len(lines), idx + _AFTER + 1)
                window = "\n".join(lines[start:end])
                masked, _ = mask_secrets(window)
                importance = rule.weight
                if primary and rule.category_code == primary:
                    importance = min(0.99, importance + 0.05)
                results.append(
                    EvidenceCandidate(
                        evidence_type=EvidenceType.LOG_LINE.value,
                        source_name=loaded.original_filename,
                        uploaded_file_id=loaded.file_id,
                        line_start=start + 1,
                        line_end=end,
                        raw_excerpt=masked,
                        normalized_excerpt=masked.strip(),
                        explanation=f"Matched rule '{rule.name}' for {rule.category_code}.",
                        importance_score=round(importance, 4),
                        metadata={"rule": rule.name, "subtype": rule.category_code},
                        category_code=rule.category_code,
                    )
                )
                break
        return results

    def _from_stack_traces(self, loaded, lines: list[str]) -> list[EvidenceCandidate]:
        text = "\n".join(lines)
        matches = list(_STACK_TRACE.finditer(text))
        if not matches:
            return []
        # Capture contiguous traceback blocks loosely via line scan.
        results: list[EvidenceCandidate] = []
        for i, line in enumerate(lines):
            if "Traceback (most recent call last)" in line or line.strip().startswith('File "'):
                start = i
                end = min(len(lines), i + 15)
                window = "\n".join(lines[start:end])
                masked, _ = mask_secrets(window)
                results.append(
                    EvidenceCandidate(
                        evidence_type=EvidenceType.STACK_TRACE.value,
                        source_name=loaded.original_filename,
                        uploaded_file_id=loaded.file_id,
                        line_start=start + 1,
                        line_end=end,
                        raw_excerpt=masked,
                        normalized_excerpt=masked.strip(),
                        explanation="Stack trace fragment extracted from log output.",
                        importance_score=0.80,
                        metadata={"subtype": "stack_trace"},
                    )
                )
                if len(results) >= 3:
                    break
        return results
