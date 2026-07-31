"""Failure taxonomy registry wrapping frozen category codes (Phase 6A.3).

Hierarchy levels:
- Level 1 — failure domain (APPLICATION, TEST, …)
- Level 2 — failure family (COMPILATION, IAM_POLICY, …)
- Level 3 — specific known failure = existing frozen ``failure_categories.code``

Does not rename, remove, or replace frozen identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

MAPPING_VERSION = "v1"

LEVEL1_APPLICATION = "APPLICATION"
LEVEL1_TEST = "TEST"
LEVEL1_DEPENDENCY = "DEPENDENCY"
LEVEL1_WORKFLOW = "WORKFLOW"
LEVEL1_INFRASTRUCTURE = "INFRASTRUCTURE"
LEVEL1_SECURITY = "SECURITY"
LEVEL1_NETWORK = "NETWORK"
LEVEL1_RESOURCE = "RESOURCE"
LEVEL1_UNKNOWN = "UNKNOWN"

LEVEL1_LABELS: dict[str, str] = {
    LEVEL1_APPLICATION: "Application",
    LEVEL1_TEST: "Test",
    LEVEL1_DEPENDENCY: "Dependency",
    LEVEL1_WORKFLOW: "Workflow",
    LEVEL1_INFRASTRUCTURE: "Infrastructure",
    LEVEL1_SECURITY: "Security",
    LEVEL1_NETWORK: "Network",
    LEVEL1_RESOURCE: "Resource",
    LEVEL1_UNKNOWN: "Unknown",
}

LEVEL2_LABELS: dict[str, str] = {
    "COMPILATION": "Compilation",
    "UNIT_TEST": "Unit test",
    "PACKAGE_RESOLUTION": "Package resolution",
    "YAML_CONFIGURATION": "YAML configuration",
    "TERRAFORM": "Terraform",
    "CONTAINER": "Container",
    "DEPLOYMENT": "Deployment",
    "IAM_POLICY": "IAM policy",
    "SECURITY_POLICY": "Security policy",
    "CONNECTION": "Connection",
    "CI_RUNNER": "CI runner",
    "UNKNOWN": "Unknown",
    "LEGACY_UNMAPPED": "Legacy unmapped",
}

# Every seeded frozen code must appear here (or explicitly as LEGACY_UNMAPPED).
_FROZEN_HIERARCHY: dict[str, tuple[str, str, str]] = {
    "build_failure": (LEVEL1_APPLICATION, "COMPILATION", "build_failure"),
    "test_failure": (LEVEL1_TEST, "UNIT_TEST", "test_failure"),
    "dependency_failure": (LEVEL1_DEPENDENCY, "PACKAGE_RESOLUTION", "dependency_failure"),
    "configuration_failure": (LEVEL1_WORKFLOW, "YAML_CONFIGURATION", "configuration_failure"),
    "terraform_failure": (LEVEL1_INFRASTRUCTURE, "TERRAFORM", "terraform_failure"),
    "docker_failure": (LEVEL1_INFRASTRUCTURE, "CONTAINER", "docker_failure"),
    "deployment_failure": (LEVEL1_INFRASTRUCTURE, "DEPLOYMENT", "deployment_failure"),
    "aws_permission_failure": (LEVEL1_SECURITY, "IAM_POLICY", "aws_permission_failure"),
    "security_misconfiguration": (LEVEL1_SECURITY, "SECURITY_POLICY", "security_misconfiguration"),
    "network_failure": (LEVEL1_NETWORK, "CONNECTION", "network_failure"),
    "ci_runner_failure": (LEVEL1_RESOURCE, "CI_RUNNER", "ci_runner_failure"),
    "unknown_failure": (LEVEL1_UNKNOWN, "UNKNOWN", "unknown_failure"),
}

# Optional aliases → frozen code (never invent new leaf codes).
_ALIASES: dict[str, str] = {
    "aws_access_denied": "aws_permission_failure",
    "iam_permission": "aws_permission_failure",
    "npm_eresolve": "dependency_failure",
    "pip_resolve": "dependency_failure",
    "image_pull": "docker_failure",
    "workflow_yaml": "configuration_failure",
}

FROZEN_CATEGORY_CODES: frozenset[str] = frozenset(_FROZEN_HIERARCHY.keys())


@dataclass(frozen=True, slots=True)
class FailureTaxonomyPath:
    level_1_code: str
    level_1_label: str
    level_2_code: str
    level_2_label: str
    level_3_code: str
    level_3_label: str
    legacy_category_code: str
    mapping_version: str = MAPPING_VERSION
    is_active: bool = True
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "level_1_code": self.level_1_code,
            "level_1_label": self.level_1_label,
            "level_2_code": self.level_2_code,
            "level_2_label": self.level_2_label,
            "level_3_code": self.level_3_code,
            "level_3_label": self.level_3_label,
            "legacy_category_code": self.legacy_category_code,
            "mapping_version": self.mapping_version,
            "is_active": self.is_active,
            "notes": self.notes,
        }


class FailureTaxonomyRegistry:
    """Map frozen codes to hierarchy paths; reject silent unmapped drops."""

    def __init__(
        self,
        *,
        mappings: dict[str, tuple[str, str, str]] | None = None,
        aliases: dict[str, str] | None = None,
        mapping_version: str = MAPPING_VERSION,
    ) -> None:
        self.mapping_version = mapping_version
        self._aliases = {k.lower(): v.lower() for k, v in (aliases or _ALIASES).items()}
        raw = mappings if mappings is not None else dict(_FROZEN_HIERARCHY)
        self._paths: dict[str, FailureTaxonomyPath] = {}
        seen_l3: set[str] = set()
        for code, (l1, l2, l3) in raw.items():
            key = code.strip().lower()
            if key in self._paths:
                raise ValueError(f"Duplicate taxonomy mapping for '{key}'")
            if l3 in seen_l3 and l3 != key:
                raise ValueError(f"Duplicate level-3 mapping for '{l3}'")
            seen_l3.add(l3)
            self._paths[key] = FailureTaxonomyPath(
                level_1_code=l1,
                level_1_label=LEVEL1_LABELS.get(l1, l1),
                level_2_code=l2,
                level_2_label=LEVEL2_LABELS.get(l2, l2.replace("_", " ").title()),
                level_3_code=l3,
                level_3_label=l3.replace("_", " "),
                legacy_category_code=key,
                mapping_version=mapping_version,
                is_active=True,
                notes="" if key in FROZEN_CATEGORY_CODES else "non-seeded mapping",
            )
        self.validate()

    def validate(self) -> None:
        missing = sorted(FROZEN_CATEGORY_CODES - set(self._paths.keys()))
        if missing:
            raise ValueError(
                "Unmapped frozen categories (must map or document LEGACY_UNMAPPED): "
                + ", ".join(missing)
            )

    def resolve_alias(self, code: str) -> str:
        normalised = (code or "").strip().lower()
        return self._aliases.get(normalised, normalised)

    def is_valid_category(self, code: str) -> bool:
        return self.resolve_alias(code) in self._paths

    def map_code(self, code: str) -> FailureTaxonomyPath:
        normalised = self.resolve_alias(code)
        path = self._paths.get(normalised)
        if path is not None:
            return path
        # Explicit unknown / legacy-unmapped path — never silent ignore.
        return FailureTaxonomyPath(
            level_1_code=LEVEL1_UNKNOWN,
            level_1_label=LEVEL1_LABELS[LEVEL1_UNKNOWN],
            level_2_code="LEGACY_UNMAPPED",
            level_2_label=LEVEL2_LABELS["LEGACY_UNMAPPED"],
            level_3_code=normalised or "unknown",
            level_3_label=(normalised or "unknown").replace("_", " "),
            legacy_category_code=normalised or (code or ""),
            mapping_version=self.mapping_version,
            is_active=False,
            notes="Code not in frozen taxonomy; mapped to UNKNOWN/LEGACY_UNMAPPED",
        )

    def unknown_path(self) -> FailureTaxonomyPath:
        return self.map_code("unknown_failure")

    def all_paths(self) -> list[FailureTaxonomyPath]:
        return sorted(self._paths.values(), key=lambda p: p.legacy_category_code)

    def children_of(
        self, *, level_1: str | None = None, level_2: str | None = None
    ) -> list[FailureTaxonomyPath]:
        items = self.all_paths()
        if level_1:
            items = [p for p in items if p.level_1_code == level_1]
        if level_2:
            items = [p for p in items if p.level_2_code == level_2]
        return items

    def parents_of(self, code: str) -> tuple[str, str]:
        path = self.map_code(code)
        return path.level_1_code, path.level_2_code

    def unmapped_frozen_report(self, known_codes: set[str]) -> list[str]:
        """Report seeded codes missing from this registry instance."""
        return sorted(set(c.lower() for c in known_codes) - set(self._paths.keys()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "mapping_version": self.mapping_version,
            "paths": [p.to_dict() for p in self.all_paths()],
            "aliases": dict(self._aliases),
            "frozen_codes": sorted(FROZEN_CATEGORY_CODES),
        }


@lru_cache(maxsize=1)
def get_taxonomy_registry() -> FailureTaxonomyRegistry:
    return FailureTaxonomyRegistry()
