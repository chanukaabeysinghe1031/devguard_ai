"""Hierarchical mapping for frozen failure-category codes (Phase 6A).

Delegates to :class:`FailureTaxonomyRegistry` (Phase 6A.3). Preserves the
public ``map_failure_category`` helper used by parsers/tests.
"""

from __future__ import annotations

from typing import Any

from app.domain.classification.taxonomy_registry import (
    LEVEL1_APPLICATION,
    LEVEL1_DEPENDENCY,
    LEVEL1_INFRASTRUCTURE,
    LEVEL1_NETWORK,
    LEVEL1_RESOURCE,
    LEVEL1_SECURITY,
    LEVEL1_TEST,
    LEVEL1_UNKNOWN,
    LEVEL1_WORKFLOW,
    get_taxonomy_registry,
)

__all__ = [
    "LEVEL1_APPLICATION",
    "LEVEL1_DEPENDENCY",
    "LEVEL1_INFRASTRUCTURE",
    "LEVEL1_NETWORK",
    "LEVEL1_RESOURCE",
    "LEVEL1_SECURITY",
    "LEVEL1_TEST",
    "LEVEL1_UNKNOWN",
    "LEVEL1_WORKFLOW",
    "map_failure_category",
]


def map_failure_category(code: str) -> dict[str, Any]:
    """Map a frozen failure-category code to the Phase 6A hierarchy.

    Unknown codes fall back to UNKNOWN/LEGACY_UNMAPPED while preserving the
    original ``legacy_code``.
    """
    path = get_taxonomy_registry().map_code(code)
    return {
        "level_1": path.level_1_code,
        "level_2": path.level_2_code,
        "level_3": path.level_3_code,
        "legacy_code": path.legacy_category_code,
    }
