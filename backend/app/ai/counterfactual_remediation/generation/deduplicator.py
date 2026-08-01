"""Candidate deduplication for remediation generation."""

from __future__ import annotations

import hashlib
import logging

from app.domain.counterfactual_remediation.generation_enums import RemediationGeneratorType
from app.domain.counterfactual_remediation.generation_versions import (
    REMEDIATION_DEDUPLICATOR_VERSION,
)
from app.domain.counterfactual_remediation.models import CounterfactualRemediationCandidate

logger = logging.getLogger(__name__)


class RemediationCandidateDeduplicator:
    """Deduplicate near-identical candidates while preserving distinct mechanisms."""

    def __init__(self, *, similarity_threshold: float = 0.88) -> None:
        self._threshold = similarity_threshold
        self.version = REMEDIATION_DEDUPLICATOR_VERSION

    def fingerprint(self, candidate: CounterfactualRemediationCandidate) -> str:
        parts = [
            candidate.hypothesis_id or "",
            candidate.template_id or "",
            "|".join(sorted(candidate.affected_artifact_ids)),
            "|".join(
                sorted(
                    {
                        (c.target_property or "")
                        for c in candidate.changes
                        if c.target_property
                    }
                )
            ),
            "|".join(
                sorted(
                    {
                        (c.normalized_diff or f"{c.original_fragment}->{c.proposed_fragment}")
                        for c in candidate.changes
                    }
                )
            ),
            str(candidate.expected_failure_condition or ""),
            candidate.summary or "",
        ]
        raw = "\n".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def deduplicate(
        self,
        candidates: list[CounterfactualRemediationCandidate],
    ) -> list[CounterfactualRemediationCandidate]:
        kept: list[CounterfactualRemediationCandidate] = []
        seen_fps: dict[str, CounterfactualRemediationCandidate] = {}

        for candidate in candidates:
            fp = self.fingerprint(candidate)
            candidate.deduplication_fingerprint = fp
            if f"dedupe_fp:{fp[:16]}" not in candidate.assumptions:
                candidate.assumptions = list(candidate.assumptions) + [f"dedupe_fp:{fp[:16]}"]

            duplicate_of = None
            for existing_fp, existing in seen_fps.items():
                if existing_fp == fp or self._materially_same(candidate, existing):
                    duplicate_of = existing
                    break
            if duplicate_of is not None:
                self._merge_provenance(duplicate_of, candidate)
                continue
            seen_fps[fp] = candidate
            kept.append(candidate)

        logger.debug("deduplicated in=%s out=%s", len(candidates), len(kept))
        return kept

    def _merge_provenance(
        self,
        survivor: CounterfactualRemediationCandidate,
        duplicate: CounterfactualRemediationCandidate,
    ) -> None:
        prov = dict(survivor.generation_provenance or {})
        gens = list(prov.get("generators") or [])
        for src in (
            survivor.generator_type,
            duplicate.generator_type,
            *(duplicate.generation_provenance or {}).get("generators", []),
        ):
            if src and src not in gens:
                gens.append(str(src))
        if len({g for g in gens if g}) > 1:
            survivor.generator_type = RemediationGeneratorType.HYBRID.value
        prov["generators"] = gens
        survivor.generation_provenance = prov
        note = f"also_from:{duplicate.generator_type}:{duplicate.generator_name}"
        if note not in survivor.assumptions:
            survivor.assumptions = list(survivor.assumptions) + [note]

    def _materially_same(
        self,
        a: CounterfactualRemediationCandidate,
        b: CounterfactualRemediationCandidate,
    ) -> bool:
        if a.hypothesis_id != b.hypothesis_id:
            return False
        if a.template_id != b.template_id:
            return False
        if set(a.affected_artifact_ids) != set(b.affected_artifact_ids):
            return False
        props_a = {(c.target_property or "") for c in a.changes}
        props_b = {(c.target_property or "") for c in b.changes}
        if props_a != props_b:
            return False
        # Distinct mechanisms must not collapse.
        types_a = {
            c.change_type.value if hasattr(c.change_type, "value") else str(c.change_type)
            for c in a.changes
        }
        types_b = {
            c.change_type.value if hasattr(c.change_type, "value") else str(c.change_type)
            for c in b.changes
        }
        if types_a != types_b:
            return False
        diffs_a = "\n".join(sorted((c.normalized_diff or c.proposed_fragment or "") for c in a.changes))
        diffs_b = "\n".join(sorted((c.normalized_diff or c.proposed_fragment or "") for c in b.changes))
        if not diffs_a or not diffs_b:
            return a.summary == b.summary and a.title == b.title
        return self._similarity(diffs_a, diffs_b) >= self._threshold

    def _similarity(self, a: str, b: str) -> float:
        if a == b:
            return 1.0
        # Token Jaccard as deterministic cheap similarity.
        ta = set(a.split())
        tb = set(b.split())
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)
