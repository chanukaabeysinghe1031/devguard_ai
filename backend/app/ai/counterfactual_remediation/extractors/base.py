"""RemediationConstraintExtractor protocol / ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from app.ai.counterfactual_remediation.model_types import (
    ConstraintExtractionResult,
    CounterfactualRemediationContext,
    RemediationCurrentState,
)
from app.domain.counterfactual_remediation.enums import RemediationArtifactType


@runtime_checkable
class RemediationConstraintExtractor(Protocol):
    """Common extractor contract (brief §15)."""

    @property
    def extractor_name(self) -> str: ...

    @property
    def extractor_version(self) -> str: ...

    @property
    def supported_artifact_types(self) -> frozenset[RemediationArtifactType]: ...

    def is_available(self) -> bool: ...

    def extract(
        self,
        context: CounterfactualRemediationContext,
        current_state: RemediationCurrentState,
    ) -> ConstraintExtractionResult: ...

    def validate_output(self, result: ConstraintExtractionResult) -> list[str]: ...

    def limitations(self) -> list[str]: ...


class BaseRemediationConstraintExtractor(ABC):
    """ABC helper implementing shared validation defaults."""

    extractor_name: str = "base"
    extractor_version: str = "constraint_extractor_v1"
    supported_artifact_types: frozenset[RemediationArtifactType] = frozenset()

    def is_available(self) -> bool:
        return True

    @abstractmethod
    def extract(
        self,
        context: CounterfactualRemediationContext,
        current_state: RemediationCurrentState,
    ) -> ConstraintExtractionResult:
        raise NotImplementedError

    def validate_output(self, result: ConstraintExtractionResult) -> list[str]:
        errors: list[str] = []
        if result.extracted_count != len(result.constraints):
            errors.append("extracted_count_mismatch")
        keys = [c.constraint_key for c in result.constraints]
        if len(keys) != len(set(keys)):
            errors.append("duplicate_constraint_keys_in_extractor_output")
        for constraint in result.constraints:
            if not constraint.constraint_key:
                errors.append("missing_constraint_key")
            if constraint.extraction_method == "llm_only" and constraint.is_blocking:
                errors.append("llm_only_blocking_constraint_forbidden")
        return errors

    def limitations(self) -> list[str]:
        return [
            "deterministic_parser_graph_only",
            "not_a_runtime_verifier",
            "no_command_execution",
        ]
