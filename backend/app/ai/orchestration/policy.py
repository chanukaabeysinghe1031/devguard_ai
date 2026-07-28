"""Versioned routing policy configuration and stable hash."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RoutingPolicyConfig:
    policy_name: str = "confidence_cost_policy"
    policy_version: str = "v1"
    confidence_high_threshold: float = 0.85
    confidence_medium_threshold: float = 0.60
    uncertainty_high_threshold: float = 0.70
    uncertainty_medium_threshold: float = 0.40
    min_evidence_quality_for_deterministic: float = 0.75
    min_retrieval_quality_for_reasoning: float = 0.55
    high_risk_requires_validation: bool = True
    enable_confidence_routing: bool = True
    enable_rag: bool = False
    enable_llm: bool = False
    enable_local_reasoner: bool = True
    enable_external_llm: bool = False
    max_provider_calls: int = 2
    max_retrieval_calls: int = 2
    max_latency_ms: int = 30_000
    max_budget_usd: Decimal | None = None

    def validate(self) -> None:
        if not (0 <= self.confidence_medium_threshold < self.confidence_high_threshold <= 1):
            raise ValueError("Invalid confidence thresholds.")
        if not (0 <= self.uncertainty_medium_threshold < self.uncertainty_high_threshold <= 1):
            raise ValueError("Invalid uncertainty thresholds.")
        if not (0 <= self.min_evidence_quality_for_deterministic <= 1):
            raise ValueError("Invalid evidence quality threshold.")
        if not (0 <= self.min_retrieval_quality_for_reasoning <= 1):
            raise ValueError("Invalid retrieval quality threshold.")

    def configuration_hash(self) -> str:
        payload = {
            "policy_name": self.policy_name,
            "policy_version": self.policy_version,
            "confidence_high_threshold": self.confidence_high_threshold,
            "confidence_medium_threshold": self.confidence_medium_threshold,
            "uncertainty_high_threshold": self.uncertainty_high_threshold,
            "uncertainty_medium_threshold": self.uncertainty_medium_threshold,
            "min_evidence_quality_for_deterministic": (self.min_evidence_quality_for_deterministic),
            "min_retrieval_quality_for_reasoning": self.min_retrieval_quality_for_reasoning,
            "high_risk_requires_validation": self.high_risk_requires_validation,
            "enable_confidence_routing": self.enable_confidence_routing,
            "enable_rag": self.enable_rag,
            "enable_llm": self.enable_llm,
            "enable_local_reasoner": self.enable_local_reasoner,
            "enable_external_llm": self.enable_external_llm,
            "max_provider_calls": self.max_provider_calls,
            "max_retrieval_calls": self.max_retrieval_calls,
            "max_latency_ms": self.max_latency_ms,
            "max_budget_usd": (
                str(self.max_budget_usd) if self.max_budget_usd is not None else None
            ),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
