"""Candidate deduplication for hybrid retrieval."""

from __future__ import annotations

import hashlib
import re

from app.ai.rag.models import RetrievalCandidate

_WS = re.compile(r"\s+")


def content_hash(text: str) -> str:
    normalised = _WS.sub(" ", (text or "").strip().lower())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


class CandidateDeduplicator:
    """Retain highest-scoring near-duplicates; preserve independent sources."""

    def deduplicate(
        self,
        candidates: list[RetrievalCandidate],
    ) -> tuple[list[RetrievalCandidate], int]:
        if not candidates:
            return [], 0

        ordered = sorted(
            candidates,
            key=lambda c: (
                -(c.hybrid_score if c.hybrid_score is not None else c.semantic_score or 0.0),
                c.candidate_id,
            ),
        )
        kept: list[RetrievalCandidate] = []
        seen_hashes: set[str] = set()
        seen_keys: set[str] = set()
        duplicates = 0

        for candidate in ordered:
            digest = content_hash(candidate.content_excerpt[:400])
            source_chunk = f"{candidate.source_id}:{candidate.chunk_id or candidate.candidate_id}"
            near = _normalised_prefix(candidate.content_excerpt)
            if digest in seen_hashes or source_chunk in seen_keys or near in seen_keys:
                duplicates += 1
                continue
            seen_hashes.add(digest)
            seen_keys.add(source_chunk)
            seen_keys.add(near)
            kept.append(candidate)
        return kept, duplicates


def _normalised_prefix(text: str) -> str:
    return _WS.sub(" ", (text or "").strip().lower())[:160]
