"""Within-hypothesis query deduplication."""

from __future__ import annotations

from app.domain.hypothesis_retrieval.models import HypothesisRetrievalQuerySpec


class HypothesisQueryDeduplicator:
    """Deduplicate query specs within a single hypothesis session only."""

    def deduplicate(
        self, specs: list[HypothesisRetrievalQuerySpec]
    ) -> tuple[list[HypothesisRetrievalQuerySpec], int]:
        kept: list[HypothesisRetrievalQuerySpec] = []
        seen: set[str] = set()
        duplicates = 0
        for spec in specs:
            key = self._key(spec)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            kept.append(spec)
        return kept, duplicates

    @staticmethod
    def _key(spec: HypothesisRetrievalQuerySpec) -> str:
        intent = str((spec.metadata or {}).get("intent_type") or "")
        identifiers = tuple(sorted(str(x) for x in (spec.target_resource_identifiers or [])[:8]))
        sources = tuple(sorted(s.value for s in spec.source_types))
        relation = spec.expected_relation.value
        paths = tuple(sorted(spec.target_paths or []))
        return "|".join(
            [
                spec.normalized_query,
                intent,
                ",".join(identifiers),
                ",".join(sources),
                relation,
                ",".join(paths),
            ]
        )
