"""Shared IR metrics for the human-gold retrieval benchmark."""

from __future__ import annotations

import math
from collections.abc import Iterable


def dcg(relevances: list[float]) -> float:
    total = 0.0
    for idx, rel in enumerate(relevances):
        total += (2**rel - 1) / math.log2(idx + 2)
    return total


def ndcg_at_k(retrieved_grades: list[float], ideal_grades: list[float], k: int) -> float:
    gains = retrieved_grades[:k]
    ideal = sorted(ideal_grades, reverse=True)[:k]
    denom = dcg(ideal)
    if denom <= 0:
        return 0.0
    return dcg(gains) / denom


def precision_at_k(binary_hits: list[int], k: int) -> float:
    if k <= 0:
        return 0.0
    window = binary_hits[:k]
    if not window:
        return 0.0
    return sum(window) / float(k)


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    hit = {doc_id for doc_id in retrieved_ids[:k] if doc_id in relevant_ids}
    return len(hit) / float(len(relevant_ids))


def average_precision(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    if not relevant_ids:
        return 0.0
    hit_count = 0
    precision_sum = 0.0
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            hit_count += 1
            precision_sum += hit_count / float(rank)
    if hit_count == 0:
        return 0.0
    return precision_sum / float(len(relevant_ids))


def reciprocal_rank(binary_hits: list[int]) -> float:
    for idx, hit in enumerate(binary_hits, start=1):
        if hit:
            return 1.0 / float(idx)
    return 0.0


def hit_rate(binary_hits: list[int], k: int | None = None) -> float:
    window = binary_hits if k is None else binary_hits[:k]
    return 1.0 if any(window) else 0.0


def mean(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / float(len(items))
