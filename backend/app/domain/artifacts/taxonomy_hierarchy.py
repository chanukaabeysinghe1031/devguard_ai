"""Hierarchical mapping for frozen failure-category codes (Phase 6A).

Maps existing seeded codes onto Level-1 / Level-2 / Level-3 labels without
renaming or replacing the frozen taxonomy identifiers.
"""

from __future__ import annotations

from typing import Any

# Level-1 vocabulary (stable research hierarchy labels).
LEVEL1_APPLICATION = "APPLICATION"
LEVEL1_TEST = "TEST"
LEVEL1_DEPENDENCY = "DEPENDENCY"
LEVEL1_WORKFLOW = "WORKFLOW"
LEVEL1_INFRASTRUCTURE = "INFRASTRUCTURE"
LEVEL1_SECURITY = "SECURITY"
LEVEL1_NETWORK = "NETWORK"
LEVEL1_RESOURCE = "RESOURCE"
LEVEL1_UNKNOWN = "UNKNOWN"

# code -> (level_1, level_2, level_3)
_FAILURE_CATEGORY_HIERARCHY: dict[str, tuple[str, str, str | None]] = {
    "build_failure": (LEVEL1_APPLICATION, "build", None),
    "test_failure": (LEVEL1_TEST, "test", None),
    "dependency_failure": (LEVEL1_DEPENDENCY, "dependency", None),
    "configuration_failure": (LEVEL1_WORKFLOW, "configuration", None),
    "terraform_failure": (LEVEL1_INFRASTRUCTURE, "terraform", None),
    "docker_failure": (LEVEL1_INFRASTRUCTURE, "docker", None),
    "deployment_failure": (LEVEL1_INFRASTRUCTURE, "deployment", None),
    "aws_permission_failure": (LEVEL1_SECURITY, "aws_permission", None),
    "security_misconfiguration": (LEVEL1_SECURITY, "misconfiguration", None),
    "network_failure": (LEVEL1_NETWORK, "network", None),
    "ci_runner_failure": (LEVEL1_RESOURCE, "ci_runner", None),
    "unknown_failure": (LEVEL1_UNKNOWN, "unknown", None),
}


def map_failure_category(code: str) -> dict[str, Any]:
    """Map a frozen failure-category code to the Phase 6A hierarchy.

    Unknown codes fall back to UNKNOWN while preserving the original
    ``legacy_code``.
    """
    normalised = (code or "").strip().lower()
    mapping = _FAILURE_CATEGORY_HIERARCHY.get(normalised)
    if mapping is None:
        return {
            "level_1": LEVEL1_UNKNOWN,
            "level_2": "unmapped",
            "level_3": None,
            "legacy_code": code,
        }
    level_1, level_2, level_3 = mapping
    return {
        "level_1": level_1,
        "level_2": level_2,
        "level_3": level_3,
        "legacy_code": normalised,
    }
