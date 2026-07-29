"""Versioned hybrid retrieval weight profiles and stable configuration hash."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class HybridWeightProfile:
    name: str
    policy_version: str
    semantic_weight: float = 0.30
    keyword_weight: float = 0.08
    error_code_weight: float = 0.16
    category_weight: float = 0.12
    stage_weight: float = 0.07
    technology_weight: float = 0.08
    stack_trace_weight: float = 0.10
    resource_weight: float = 0.05
    authority_weight: float = 0.04
    recency_weight: float = 0.0
    history_quality_weight: float = 0.0
    duplicate_penalty: float = 0.15
    category_mismatch_penalty: float = 0.08
    technology_mismatch_penalty: float = 0.05
    stale_penalty: float = 0.0
    min_candidate_score: float = 0.15
    min_semantic_score: float = 0.05
    min_exact_match_score: float = 0.50
    min_history_quality_score: float = 0.70
    max_candidates_before_rerank: int = 30
    max_final_results: int = 6
    max_chunks_per_document: int = 2
    max_historical_results: int = 2
    diversity_lambda: float = 0.75
    enable_lexical: bool = True
    enable_diversity: bool = True
    enable_stack_trace: bool = True
    enable_historical: bool = False

    def configuration_hash(self) -> str:
        payload = asdict(self)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


EMBEDDING_BASELINE_V1 = HybridWeightProfile(
    name="embedding_baseline_v1",
    policy_version="v1",
    semantic_weight=1.0,
    keyword_weight=0.0,
    error_code_weight=0.0,
    category_weight=0.0,
    stage_weight=0.0,
    technology_weight=0.0,
    stack_trace_weight=0.0,
    resource_weight=0.0,
    authority_weight=0.0,
    recency_weight=0.0,
    history_quality_weight=0.0,
    enable_lexical=False,
    enable_diversity=False,
    enable_stack_trace=False,
    enable_historical=False,
    max_final_results=5,
)

HYBRID_STATIC_V1 = HybridWeightProfile(
    name="hybrid_static_v1",
    policy_version="v1",
    semantic_weight=0.30,
    keyword_weight=0.08,
    error_code_weight=0.16,
    category_weight=0.12,
    stage_weight=0.07,
    technology_weight=0.08,
    stack_trace_weight=0.10,
    resource_weight=0.05,
    authority_weight=0.04,
    recency_weight=0.0,
    history_quality_weight=0.0,
    enable_lexical=True,
    enable_diversity=True,
    enable_stack_trace=True,
    enable_historical=False,
)

HYBRID_HISTORY_V1 = HybridWeightProfile(
    name="hybrid_history_v1",
    policy_version="v1",
    semantic_weight=0.26,
    keyword_weight=0.06,
    error_code_weight=0.14,
    category_weight=0.10,
    stage_weight=0.06,
    technology_weight=0.07,
    stack_trace_weight=0.08,
    resource_weight=0.04,
    authority_weight=0.03,
    recency_weight=0.03,
    history_quality_weight=0.12,
    enable_lexical=True,
    enable_diversity=True,
    enable_stack_trace=True,
    enable_historical=True,
)

_PROFILES: dict[str, HybridWeightProfile] = {
    EMBEDDING_BASELINE_V1.name: EMBEDDING_BASELINE_V1,
    HYBRID_STATIC_V1.name: HYBRID_STATIC_V1,
    HYBRID_HISTORY_V1.name: HYBRID_HISTORY_V1,
}


def get_weight_profile(name: str | None) -> HybridWeightProfile:
    if not name:
        return HYBRID_STATIC_V1
    if name not in _PROFILES:
        raise ValueError(f"Unknown hybrid weight profile: {name}")
    return _PROFILES[name]


@dataclass
class HybridRetrievalSettings:
    """Runtime knobs merged from server config (not secrets)."""

    default_mode: str = "hybrid_static"
    enable_hybrid_retrieval: bool = True
    enable_historical_retrieval: bool = False
    enable_lexical_retrieval: bool = True
    enable_stack_trace_similarity: bool = True
    enable_retrieval_diversity: bool = True
    weight_profile_name: str = "hybrid_static_v1"
    profile_overrides: dict[str, float] = field(default_factory=dict)

    def resolve_profile(self, mode: str) -> HybridWeightProfile:
        if mode == "embedding_only":
            base = EMBEDDING_BASELINE_V1
        elif mode == "hybrid_with_history":
            base = HYBRID_HISTORY_V1
        else:
            base = get_weight_profile(self.weight_profile_name)
        # Apply feature-flag gates without mutating frozen baseline identities.
        return HybridWeightProfile(
            **{
                **asdict(base),
                "enable_lexical": base.enable_lexical and self.enable_lexical_retrieval,
                "enable_diversity": base.enable_diversity and self.enable_retrieval_diversity,
                "enable_stack_trace": (
                    base.enable_stack_trace and self.enable_stack_trace_similarity
                ),
                "enable_historical": (base.enable_historical and self.enable_historical_retrieval),
            }
        )
