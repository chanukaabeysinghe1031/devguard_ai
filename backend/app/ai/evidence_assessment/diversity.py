"""Evidence diversity scoring with duplicate penalty."""

from __future__ import annotations

from collections import Counter


def diversity_score(
    *,
    source_types: list[str],
    text_hashes: list[str | None],
    source_paths: list[str | None],
) -> float:
    """
    Score diversity in [0, 1].

    Rewards distinct source types; penalizes duplicate text hashes / paths.
    """
    if not source_types:
        return 0.0

    unique_types = len(set(source_types))
    type_score = min(1.0, unique_types / 4.0)

    hashes = [h for h in text_hashes if h]
    paths = [p for p in source_paths if p]
    n = max(len(source_types), 1)
    hash_dupes = sum(c - 1 for c in Counter(hashes).values() if c > 1)
    path_dupes = sum(c - 1 for c in Counter(paths).values() if c > 1)
    dupe_penalty = min(0.6, (hash_dupes + path_dupes) / n)

    return max(0.0, min(1.0, type_score * (1.0 - dupe_penalty)))
