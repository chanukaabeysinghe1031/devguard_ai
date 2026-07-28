"""Backward-compatible export for Module 8 router."""

from app.ai.orchestration.adaptive_router import AdaptiveExecutionRouter, ConfidenceCostRouter
from app.ai.orchestration.policy import RoutingPolicyConfig

__all__ = ["AdaptiveExecutionRouter", "ConfidenceCostRouter", "RoutingPolicyConfig"]
