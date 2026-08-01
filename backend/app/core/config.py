"""Application configuration via Pydantic Settings."""

import json
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Any, Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    project_name: str = Field(default="DevGuard AI", alias="PROJECT_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        alias="ENVIRONMENT",
    )
    debug: bool = Field(default=False, alias="DEBUG")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    service_name: str = Field(default="devguard-api", alias="SERVICE_NAME")

    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_user: str = Field(default="devguard", alias="POSTGRES_USER")
    postgres_password: str = Field(default="change_me", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="devguard", alias="POSTGRES_DB")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    backend_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        alias="BACKEND_CORS_ORIGINS",
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: Literal["json", "console"] = Field(default="json", alias="LOG_FORMAT")

    # Development-only bootstrap seed settings. Never enable in production.
    bootstrap_enabled: bool = Field(default=False, alias="BOOTSTRAP_ENABLED")
    bootstrap_org_name: str = Field(default="DevGuard Default", alias="BOOTSTRAP_ORG_NAME")
    bootstrap_org_slug: str = Field(default="default", alias="BOOTSTRAP_ORG_SLUG")
    bootstrap_owner_email: str = Field(
        default="owner@devguard.local",
        alias="BOOTSTRAP_OWNER_EMAIL",
    )
    bootstrap_owner_password: str = Field(default="", alias="BOOTSTRAP_OWNER_PASSWORD")
    bootstrap_owner_full_name: str = Field(
        default="DevGuard Owner",
        alias="BOOTSTRAP_OWNER_FULL_NAME",
    )

    # JWT / authentication (Module 3). Never commit real secrets.
    jwt_secret_key: str = Field(default="", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_issuer: str = Field(default="devguard-ai", alias="JWT_ISSUER")
    access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # File upload / local storage (Module 5).
    file_storage_backend: str = Field(default="local", alias="FILE_STORAGE_BACKEND")
    file_storage_path: str = Field(default="./storage/uploads", alias="FILE_STORAGE_PATH")
    max_upload_size_bytes: int = Field(default=10_485_760, alias="MAX_UPLOAD_SIZE_BYTES")
    max_files_per_upload: int = Field(default=10, alias="MAX_FILES_PER_UPLOAD")

    # AI pipeline (Modules 6–8). Deterministic rules path is always available.
    enable_rag: bool = Field(default=False, alias="ENABLE_RAG")
    enable_llm: bool = Field(default=False, alias="ENABLE_LLM")
    enable_local_reasoner: bool = Field(default=True, alias="ENABLE_LOCAL_REASONER")
    enable_external_llm: bool = Field(default=False, alias="ENABLE_EXTERNAL_LLM")
    enable_confidence_routing: bool = Field(default=True, alias="ENABLE_CONFIDENCE_ROUTING")
    enable_cost_tracking: bool = Field(default=True, alias="ENABLE_COST_TRACKING")
    enable_latency_budget: bool = Field(default=True, alias="ENABLE_LATENCY_BUDGET")
    analysis_execution_mode: Literal["background", "sync"] = Field(
        default="background",
        alias="ANALYSIS_EXECUTION_MODE",
    )
    rag_backend: Literal["memory", "chroma"] = Field(default="memory", alias="RAG_BACKEND")
    embedding_provider: Literal["hash", "sentence_transformers"] = Field(
        default="hash",
        alias="EMBEDDING_PROVIDER",
    )
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL",
    )
    embedding_device: Literal["cpu", "mps", "cuda", "auto"] = Field(
        default="cpu",
        alias="EMBEDDING_DEVICE",
    )
    embedding_batch_size: int = Field(default=16, alias="EMBEDDING_BATCH_SIZE")
    embedding_normalize: bool = Field(default=True, alias="EMBEDDING_NORMALIZE")
    embedding_max_input_characters: int = Field(
        default=12_000,
        alias="EMBEDDING_MAX_INPUT_CHARACTERS",
    )
    embedding_strict_startup_validation: bool = Field(
        default=False,
        alias="EMBEDDING_STRICT_STARTUP_VALIDATION",
    )
    llm_provider: Literal["local", "openai"] = Field(default="local", alias="LLM_PROVIDER")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_timeout_seconds: float = Field(default=30.0, alias="OPENAI_TIMEOUT_SECONDS")
    openai_max_retries: int = Field(default=3, alias="OPENAI_MAX_RETRIES")
    openai_retry_base_delay_ms: int = Field(default=500, alias="OPENAI_RETRY_BASE_DELAY_MS")
    openai_retry_max_delay_ms: int = Field(default=8000, alias="OPENAI_RETRY_MAX_DELAY_MS")
    openai_circuit_breaker_failures: int = Field(
        default=5,
        alias="OPENAI_CIRCUIT_BREAKER_FAILURES",
    )
    openai_circuit_breaker_reset_seconds: int = Field(
        default=60,
        alias="OPENAI_CIRCUIT_BREAKER_RESET_SECONDS",
    )
    # Local embedded Chroma path (used when CHROMA_HOST is empty).
    chroma_persist_path: str = Field(default="./storage/chroma", alias="CHROMA_PERSIST_PATH")
    # Remote Chroma HTTP client (Docker service name "chroma", host port 8001).
    chroma_host: str = Field(default="", alias="CHROMA_HOST")
    chroma_port: int = Field(default=8000, alias="CHROMA_PORT")
    chroma_collection_name: str = Field(
        default="devguard_knowledge",
        alias="CHROMA_COLLECTION_NAME",
    )
    chroma_secondary_collection_name: str = Field(
        default="",
        alias="CHROMA_SECONDARY_COLLECTION_NAME",
    )
    chroma_tenant: str = Field(default="default_tenant", alias="CHROMA_TENANT")
    chroma_database: str = Field(default="default_database", alias="CHROMA_DATABASE")
    knowledge_base_path: str = Field(default="../knowledge_base", alias="KNOWLEDGE_BASE_PATH")
    rag_top_k: int = Field(default=10, alias="RAG_TOP_K")
    rag_context_k: int = Field(default=5, alias="RAG_CONTEXT_K")
    default_execution_mode: Literal[
        "rules_only",
        "rules_rag",
        "llm_only",
        "rag_llm",
        "confidence_routed",
    ] = Field(default="confidence_routed", alias="DEFAULT_EXECUTION_MODE")
    default_budget_usd: Decimal | None = Field(default=None, alias="DEFAULT_BUDGET_USD")
    max_budget_usd_per_analysis: Decimal | None = Field(
        default=None,
        alias="MAX_BUDGET_USD_PER_ANALYSIS",
    )
    default_latency_limit_ms: int = Field(default=30_000, alias="DEFAULT_LATENCY_LIMIT_MS")
    max_latency_limit_ms: int = Field(default=60_000, alias="MAX_LATENCY_LIMIT_MS")
    confidence_high_threshold: float = Field(default=0.85, alias="CONFIDENCE_HIGH_THRESHOLD")
    confidence_medium_threshold: float = Field(default=0.60, alias="CONFIDENCE_MEDIUM_THRESHOLD")
    uncertainty_high_threshold: float = Field(default=0.70, alias="UNCERTAINTY_HIGH_THRESHOLD")
    uncertainty_medium_threshold: float = Field(
        default=0.40,
        alias="UNCERTAINTY_MEDIUM_THRESHOLD",
    )
    min_evidence_quality_for_deterministic: float = Field(
        default=0.75,
        alias="MIN_EVIDENCE_QUALITY_FOR_DETERMINISTIC",
    )
    min_retrieval_quality_for_reasoning: float = Field(
        default=0.55,
        alias="MIN_RETRIEVAL_QUALITY_FOR_REASONING",
    )
    high_risk_requires_validation: bool = Field(
        default=True,
        alias="HIGH_RISK_REQUIRES_VALIDATION",
    )
    max_provider_calls_per_analysis: int = Field(
        default=2,
        alias="MAX_PROVIDER_CALLS_PER_ANALYSIS",
    )
    max_llm_input_tokens: int = Field(default=6000, alias="MAX_LLM_INPUT_TOKENS")
    max_llm_output_tokens: int = Field(default=1500, alias="MAX_LLM_OUTPUT_TOKENS")
    max_retrieval_calls_per_analysis: int = Field(
        default=2,
        alias="MAX_RETRIEVAL_CALLS_PER_ANALYSIS",
    )
    llm_input_cost_usd_per_million_tokens: Decimal | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LLM_INPUT_COST_USD_PER_MILLION_TOKENS",
            "OPENAI_INPUT_COST_PER_1M_TOKENS",
        ),
    )
    llm_output_cost_usd_per_million_tokens: Decimal | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LLM_OUTPUT_COST_USD_PER_MILLION_TOKENS",
            "OPENAI_OUTPUT_COST_PER_1M_TOKENS",
        ),
    )
    embedding_cost_usd_per_million_tokens: Decimal | None = Field(
        default=None,
        alias="EMBEDDING_COST_USD_PER_MILLION_TOKENS",
    )
    routing_policy_name: str = Field(
        default="confidence_cost_policy",
        alias="ROUTING_POLICY_NAME",
    )
    routing_policy_version: str = Field(default="v1", alias="ROUTING_POLICY_VERSION")

    # Module 9 hybrid retrieval (heuristic weights — experimental).
    default_retrieval_mode: Literal[
        "embedding_only",
        "hybrid_static",
        "hybrid_with_history",
        "keyword_only",
    ] = Field(default="hybrid_static", alias="DEFAULT_RETRIEVAL_MODE")
    enable_hybrid_retrieval: bool = Field(default=True, alias="ENABLE_HYBRID_RETRIEVAL")
    enable_historical_retrieval: bool = Field(
        default=False,
        alias="ENABLE_HISTORICAL_RETRIEVAL",
    )
    enable_lexical_retrieval: bool = Field(default=True, alias="ENABLE_LEXICAL_RETRIEVAL")
    enable_stack_trace_similarity: bool = Field(
        default=True,
        alias="ENABLE_STACK_TRACE_SIMILARITY",
    )
    enable_retrieval_diversity: bool = Field(default=True, alias="ENABLE_RETRIEVAL_DIVERSITY")

    # Phase 6A.1 — artifact bundle + deep parsers (causal pipeline). All OFF by default.
    causal_analysis_enabled: bool = Field(default=False, alias="CAUSAL_ANALYSIS_ENABLED")
    artifact_bundle_enabled: bool = Field(default=False, alias="ARTIFACT_BUNDLE_ENABLED")
    artifact_parsing_enabled: bool = Field(default=False, alias="ARTIFACT_PARSING_ENABLED")
    github_artifact_acquisition_enabled: bool = Field(
        default=False,
        alias="GITHUB_ARTIFACT_ACQUISITION_ENABLED",
    )
    artifact_max_content_chars: int = Field(
        default=500_000,
        alias="ARTIFACT_MAX_CONTENT_CHARS",
    )

    # Phase 6A.2 — temporal localisation + evidence graph. All OFF by default.
    temporal_localisation_enabled: bool = Field(
        default=False,
        alias="TEMPORAL_LOCALISATION_ENABLED",
    )
    evidence_graph_enabled: bool = Field(default=False, alias="EVIDENCE_GRAPH_ENABLED")
    graph_consistency_enabled: bool = Field(
        default=False,
        alias="GRAPH_CONSISTENCY_ENABLED",
    )
    evidence_graph_max_nodes: int = Field(default=2000, alias="EVIDENCE_GRAPH_MAX_NODES")
    evidence_graph_max_edges: int = Field(default=5000, alias="EVIDENCE_GRAPH_MAX_EDGES")
    temporal_max_events: int = Field(default=5000, alias="TEMPORAL_MAX_EVENTS")

    # Phase 6A.3 — hierarchical classification + open-set. All OFF by default.
    hierarchical_classification_enabled: bool = Field(
        default=False,
        alias="HIERARCHICAL_CLASSIFICATION_ENABLED",
    )
    open_set_detection_enabled: bool = Field(
        default=False,
        alias="OPEN_SET_DETECTION_ENABLED",
    )
    classification_disagreement_enabled: bool = Field(
        default=False,
        alias="CLASSIFICATION_DISAGREEMENT_ENABLED",
    )
    classification_confidence_breakdown_enabled: bool = Field(
        default=False,
        alias="CLASSIFICATION_CONFIDENCE_BREAKDOWN_ENABLED",
    )
    open_set_default_confidence_threshold: float = Field(
        default=0.55,
        alias="OPEN_SET_DEFAULT_CONFIDENCE_THRESHOLD",
    )
    open_set_default_margin_threshold: float = Field(
        default=0.08,
        alias="OPEN_SET_DEFAULT_MARGIN_THRESHOLD",
    )
    open_set_default_distance_threshold: float = Field(
        default=0.65,
        alias="OPEN_SET_DEFAULT_DISTANCE_THRESHOLD",
    )
    open_set_min_evidence_coverage: float = Field(
        default=0.25,
        alias="OPEN_SET_MIN_EVIDENCE_COVERAGE",
    )
    open_set_category_thresholds_json: str = Field(
        default="{}",
        alias="OPEN_SET_CATEGORY_THRESHOLDS_JSON",
    )

    # Phase 6A.4 — competing causal hypotheses. All OFF by default.
    causal_hypothesis_generation_enabled: bool = Field(
        default=False,
        alias="CAUSAL_HYPOTHESIS_GENERATION_ENABLED",
    )
    rule_hypothesis_generation_enabled: bool = Field(
        default=False,
        alias="RULE_HYPOTHESIS_GENERATION_ENABLED",
    )
    llm_hypothesis_generation_enabled: bool = Field(
        default=False,
        alias="LLM_HYPOTHESIS_GENERATION_ENABLED",
    )
    hypothesis_critic_enabled: bool = Field(
        default=False,
        alias="HYPOTHESIS_CRITIC_ENABLED",
    )
    max_causal_hypotheses: int = Field(default=5, alias="MAX_CAUSAL_HYPOTHESES")
    min_causal_hypotheses: int = Field(default=1, alias="MIN_CAUSAL_HYPOTHESES")
    hypothesis_graph_max_depth: int = Field(default=4, alias="HYPOTHESIS_GRAPH_MAX_DEPTH")
    hypothesis_graph_max_nodes: int = Field(default=100, alias="HYPOTHESIS_GRAPH_MAX_NODES")
    hypothesis_graph_max_edges: int = Field(default=200, alias="HYPOTHESIS_GRAPH_MAX_EDGES")
    hypothesis_max_evidence_items: int = Field(
        default=40,
        alias="HYPOTHESIS_MAX_EVIDENCE_ITEMS",
    )
    hypothesis_duplicate_similarity_threshold: float = Field(
        default=0.92,
        alias="HYPOTHESIS_DUPLICATE_SIMILARITY_THRESHOLD",
    )

    # Phase 6A.5 Part 1B — hypothesis-directed retrieval foundation.
    # Experimental path OFF by default; supporting source/cache toggles default ON.
    hypothesis_directed_rag_enabled: bool = Field(
        default=False,
        alias="HYPOTHESIS_DIRECTED_RAG_ENABLED",
    )
    multi_query_retrieval_enabled: bool = Field(
        default=False,
        alias="MULTI_QUERY_RETRIEVAL_ENABLED",
    )
    hypothesis_graph_context_enabled: bool = Field(
        default=False,
        alias="HYPOTHESIS_GRAPH_CONTEXT_ENABLED",
    )
    hypothesis_historical_retrieval_enabled: bool = Field(
        default=True,
        alias="HYPOTHESIS_HISTORICAL_RETRIEVAL_ENABLED",
    )
    hypothesis_static_kb_retrieval_enabled: bool = Field(
        default=True,
        alias="HYPOTHESIS_STATIC_KB_RETRIEVAL_ENABLED",
    )
    hypothesis_artifact_retrieval_enabled: bool = Field(
        default=True,
        alias="HYPOTHESIS_ARTIFACT_RETRIEVAL_ENABLED",
    )
    hypothesis_retrieval_persistence_enabled: bool = Field(
        default=True,
        alias="HYPOTHESIS_RETRIEVAL_PERSISTENCE_ENABLED",
    )
    retrieval_cache_enabled: bool = Field(
        default=True,
        alias="RETRIEVAL_CACHE_ENABLED",
    )
    # Reserved for Phase 6A.6+ — must remain unused in Part 1B.
    causal_ranking_enabled: bool = Field(
        default=False,
        alias="CAUSAL_RANKING_ENABLED",
    )
    max_hypotheses_for_retrieval: int = Field(
        default=5,
        alias="MAX_HYPOTHESES_FOR_RETRIEVAL",
    )
    max_queries_per_hypothesis: int = Field(
        default=6,
        alias="MAX_QUERIES_PER_HYPOTHESIS",
    )
    max_results_per_query: int = Field(default=10, alias="MAX_RESULTS_PER_QUERY")
    max_retrieved_items_per_hypothesis: int = Field(
        default=40,
        alias="MAX_RETRIEVED_ITEMS_PER_HYPOTHESIS",
    )
    max_retrieval_context_chars: int = Field(
        default=60_000,
        alias="MAX_RETRIEVAL_CONTEXT_CHARS",
    )
    max_retrieval_query_chars: int = Field(
        default=2000,
        alias="MAX_RETRIEVAL_QUERY_CHARS",
    )
    max_graph_context_nodes_for_retrieval: int = Field(
        default=80,
        alias="MAX_GRAPH_CONTEXT_NODES_FOR_RETRIEVAL",
    )
    max_graph_context_edges_for_retrieval: int = Field(
        default=150,
        alias="MAX_GRAPH_CONTEXT_EDGES_FOR_RETRIEVAL",
    )
    max_artifact_evidence_items_for_retrieval: int = Field(
        default=40,
        alias="MAX_ARTIFACT_EVIDENCE_ITEMS_FOR_RETRIEVAL",
    )
    max_historical_incidents_per_hypothesis: int = Field(
        default=10,
        alias="MAX_HISTORICAL_INCIDENTS_PER_HYPOTHESIS",
    )
    hypothesis_retrieval_timeout_seconds: float = Field(
        default=45.0,
        alias="HYPOTHESIS_RETRIEVAL_TIMEOUT_SECONDS",
    )
    max_concurrent_hypothesis_retrieval_sessions: int = Field(
        default=2,
        alias="MAX_CONCURRENT_HYPOTHESIS_RETRIEVAL_SESSIONS",
    )

    # Phase 6A.5 Part 2 — adaptive hypothesis retrieval intelligence (all OFF by default).
    adaptive_hypothesis_retrieval_enabled: bool = Field(
        default=False,
        alias="ADAPTIVE_HYPOTHESIS_RETRIEVAL_ENABLED",
    )
    hypothesis_query_expansion_enabled: bool = Field(
        default=False,
        alias="HYPOTHESIS_QUERY_EXPANSION_ENABLED",
    )
    hypothesis_source_routing_enabled: bool = Field(
        default=False,
        alias="HYPOTHESIS_SOURCE_ROUTING_ENABLED",
    )
    retrieval_result_validation_enabled: bool = Field(
        default=False,
        alias="RETRIEVAL_RESULT_VALIDATION_ENABLED",
    )
    retrieval_follow_up_enabled: bool = Field(
        default=False,
        alias="RETRIEVAL_FOLLOW_UP_ENABLED",
    )
    hypothesis_exact_identifier_boost_enabled: bool = Field(
        default=False,
        alias="HYPOTHESIS_EXACT_IDENTIFIER_BOOST_ENABLED",
    )
    hypothesis_metadata_filtering_enabled: bool = Field(
        default=False,
        alias="HYPOTHESIS_METADATA_FILTERING_ENABLED",
    )
    max_query_expansions_per_hypothesis: int = Field(
        default=4,
        alias="MAX_QUERY_EXPANSIONS_PER_HYPOTHESIS",
    )
    max_follow_up_rounds: int = Field(default=1, alias="MAX_FOLLOW_UP_ROUNDS")
    max_total_queries_per_hypothesis: int = Field(
        default=10,
        alias="MAX_TOTAL_QUERIES_PER_HYPOTHESIS",
    )
    max_source_types_per_query: int = Field(
        default=5,
        alias="MAX_SOURCE_TYPES_PER_QUERY",
    )
    min_results_before_follow_up: int = Field(
        default=2,
        alias="MIN_RESULTS_BEFORE_FOLLOW_UP",
    )
    min_retrieval_score_for_acceptance: float = Field(
        default=0.35,
        alias="MIN_RETRIEVAL_SCORE_FOR_ACCEPTANCE",
    )
    max_exact_identifiers_per_query: int = Field(
        default=8,
        alias="MAX_EXACT_IDENTIFIERS_PER_QUERY",
    )
    max_retrieval_validation_items: int = Field(
        default=50,
        alias="MAX_RETRIEVAL_VALIDATION_ITEMS",
    )
    max_graph_retrieval_depth: int = Field(
        default=4,
        alias="MAX_GRAPH_RETRIEVAL_DEPTH",
    )
    max_graph_retrieval_nodes: int = Field(
        default=80,
        alias="MAX_GRAPH_RETRIEVAL_NODES",
    )
    max_graph_retrieval_edges: int = Field(
        default=150,
        alias="MAX_GRAPH_RETRIEVAL_EDGES",
    )
    max_artifact_results_per_query: int = Field(
        default=15,
        alias="MAX_ARTIFACT_RESULTS_PER_QUERY",
    )
    max_temporal_results_per_query: int = Field(
        default=15,
        alias="MAX_TEMPORAL_RESULTS_PER_QUERY",
    )
    max_historical_results_per_query: int = Field(
        default=10,
        alias="MAX_HISTORICAL_RESULTS_PER_QUERY",
    )
    max_official_document_results_per_query: int = Field(
        default=10,
        alias="MAX_OFFICIAL_DOCUMENT_RESULTS_PER_QUERY",
    )
    max_retrieval_total_duration_seconds: float = Field(
        default=60.0,
        alias="MAX_RETRIEVAL_TOTAL_DURATION_SECONDS",
    )

    # Phase 6A.5 Part 3 — evidence assessment / ranking / candidate selection (all OFF).
    hypothesis_evidence_assessment_enabled: bool = Field(
        default=False,
        alias="HYPOTHESIS_EVIDENCE_ASSESSMENT_ENABLED",
    )
    evidence_sufficiency_enabled: bool = Field(
        default=False,
        alias="EVIDENCE_SUFFICIENCY_ENABLED",
    )
    contradiction_analysis_enabled: bool = Field(
        default=False,
        alias="CONTRADICTION_ANALYSIS_ENABLED",
    )
    hypothesis_ranking_enabled: bool = Field(
        default=False,
        alias="HYPOTHESIS_RANKING_ENABLED",
    )
    candidate_selection_enabled: bool = Field(
        default=False,
        alias="CANDIDATE_SELECTION_ENABLED",
    )
    max_evidence_assessments_per_hypothesis: int = Field(
        default=40,
        alias="MAX_EVIDENCE_ASSESSMENTS_PER_HYPOTHESIS",
    )
    max_candidate_hypotheses: int = Field(
        default=5,
        alias="MAX_CANDIDATE_HYPOTHESES",
    )
    min_ranking_score_for_top_candidate: float = Field(
        default=0.40,
        alias="MIN_RANKING_SCORE_FOR_TOP_CANDIDATE",
    )
    ranking_tie_epsilon: float = Field(
        default=0.02,
        alias="RANKING_TIE_EPSILON",
    )

    # Phase 6A.6 Part 1 — counterfactual remediation foundation (all OFF).
    # Candidates are hypothesis-conditional and unverified. No apply / verifier execution.
    counterfactual_remediation_enabled: bool = Field(
        default=False,
        alias="COUNTERFACTUAL_REMEDIATION_ENABLED",
    )
    counterfactual_constraint_extraction_enabled: bool = Field(
        default=False,
        alias="COUNTERFACTUAL_CONSTRAINT_EXTRACTION_ENABLED",
    )
    minimal_change_planning_enabled: bool = Field(
        default=False,
        alias="MINIMAL_CHANGE_PLANNING_ENABLED",
    )
    counterfactual_template_registry_enabled: bool = Field(
        default=False,
        alias="COUNTERFACTUAL_TEMPLATE_REGISTRY_ENABLED",
    )
    counterfactual_persistence_enabled: bool = Field(
        default=False,
        alias="COUNTERFACTUAL_PERSISTENCE_ENABLED",
    )
    counterfactual_debug_api_enabled: bool = Field(
        default=False,
        alias="COUNTERFACTUAL_DEBUG_API_ENABLED",
    )
    # Reserved Part 2 generation / analysis flags — remain OFF by default.
    rule_remediation_generation_enabled: bool = Field(
        default=False,
        alias="RULE_REMEDIATION_GENERATION_ENABLED",
    )
    llm_remediation_generation_enabled: bool = Field(
        default=False,
        alias="LLM_REMEDIATION_GENERATION_ENABLED",
    )
    remediation_risk_analysis_enabled: bool = Field(
        default=False,
        alias="REMEDIATION_RISK_ANALYSIS_ENABLED",
    )
    remediation_side_effect_analysis_enabled: bool = Field(
        default=False,
        alias="REMEDIATION_SIDE_EFFECT_ANALYSIS_ENABLED",
    )
    remediation_ranking_enabled: bool = Field(
        default=False,
        alias="REMEDIATION_RANKING_ENABLED",
    )
    remediation_deduplication_enabled: bool = Field(
        default=False,
        alias="REMEDIATION_DEDUPLICATION_ENABLED",
    )
    remediation_diversity_enabled: bool = Field(
        default=False,
        alias="REMEDIATION_DIVERSITY_ENABLED",
    )
    remediation_patch_rendering_enabled: bool = Field(
        default=False,
        alias="REMEDIATION_PATCH_RENDERING_ENABLED",
    )
    remediation_rollback_generation_enabled: bool = Field(
        default=False,
        alias="REMEDIATION_ROLLBACK_GENERATION_ENABLED",
    )
    remediation_reference_validation_enabled: bool = Field(
        default=False,
        alias="REMEDIATION_REFERENCE_VALIDATION_ENABLED",
    )
    remediation_constraint_validation_enabled: bool = Field(
        default=False,
        alias="REMEDIATION_CONSTRAINT_VALIDATION_ENABLED",
    )
    max_hypotheses_for_remediation: int = Field(
        default=3,
        alias="MAX_HYPOTHESES_FOR_REMEDIATION",
    )
    max_remediation_candidates_per_hypothesis: int = Field(
        default=3,
        alias="MAX_REMEDIATION_CANDIDATES_PER_HYPOTHESIS",
    )
    max_total_remediation_candidates: int = Field(
        default=8,
        alias="MAX_TOTAL_REMEDIATION_CANDIDATES",
    )
    max_constraints_per_hypothesis: int = Field(
        default=100,
        alias="MAX_CONSTRAINTS_PER_HYPOTHESIS",
    )
    max_counterfactual_context_chars: int = Field(
        default=80_000,
        alias="MAX_COUNTERFACTUAL_CONTEXT_CHARS",
    )
    max_patch_characters: int = Field(default=30_000, alias="MAX_PATCH_CHARACTERS")
    max_patch_files_per_candidate: int = Field(
        default=5,
        alias="MAX_PATCH_FILES_PER_CANDIDATE",
    )
    max_changed_lines_per_candidate: int = Field(
        default=200,
        alias="MAX_CHANGED_LINES_PER_CANDIDATE",
    )
    max_counterfactual_graph_nodes: int = Field(
        default=100,
        alias="MAX_COUNTERFACTUAL_GRAPH_NODES",
    )
    max_counterfactual_graph_edges: int = Field(
        default=200,
        alias="MAX_COUNTERFACTUAL_GRAPH_EDGES",
    )
    max_assumptions_per_candidate: int = Field(
        default=20,
        alias="MAX_ASSUMPTIONS_PER_CANDIDATE",
    )
    max_expected_effects_per_candidate: int = Field(
        default=20,
        alias="MAX_EXPECTED_EFFECTS_PER_CANDIDATE",
    )
    max_rollback_steps_per_candidate: int = Field(
        default=20,
        alias="MAX_ROLLBACK_STEPS_PER_CANDIDATE",
    )
    counterfactual_stage_timeout_seconds: float = Field(
        default=60.0,
        alias="COUNTERFACTUAL_STAGE_TIMEOUT_SECONDS",
    )
    # Phase 6A.6 Part 2 generation bounds (all generation still OFF by default).
    max_rule_candidates_per_hypothesis: int = Field(
        default=3,
        alias="MAX_RULE_CANDIDATES_PER_HYPOTHESIS",
    )
    max_llm_candidates_per_hypothesis: int = Field(
        default=2,
        alias="MAX_LLM_CANDIDATES_PER_HYPOTHESIS",
    )
    max_final_candidates_per_hypothesis: int = Field(
        default=3,
        alias="MAX_FINAL_CANDIDATES_PER_HYPOTHESIS",
    )
    max_total_final_candidates: int = Field(
        default=8,
        alias="MAX_TOTAL_FINAL_CANDIDATES",
    )
    max_candidate_files: int = Field(default=5, alias="MAX_CANDIDATE_FILES")
    max_candidate_changed_lines: int = Field(
        default=200,
        alias="MAX_CANDIDATE_CHANGED_LINES",
    )
    max_candidate_patch_characters: int = Field(
        default=30_000,
        alias="MAX_CANDIDATE_PATCH_CHARACTERS",
    )
    max_candidate_explanation_characters: int = Field(
        default=8_000,
        alias="MAX_CANDIDATE_EXPLANATION_CHARACTERS",
    )
    max_candidate_assumptions: int = Field(
        default=20,
        alias="MAX_CANDIDATE_ASSUMPTIONS",
    )
    max_candidate_limitations: int = Field(
        default=20,
        alias="MAX_CANDIDATE_LIMITATIONS",
    )
    max_candidate_expected_effects: int = Field(
        default=20,
        alias="MAX_CANDIDATE_EXPECTED_EFFECTS",
    )
    max_candidate_side_effects: int = Field(
        default=20,
        alias="MAX_CANDIDATE_SIDE_EFFECTS",
    )
    max_candidate_risk_signals: int = Field(
        default=30,
        alias="MAX_CANDIDATE_RISK_SIGNALS",
    )
    max_remediation_llm_calls_per_analysis: int = Field(
        default=3,
        alias="MAX_REMEDIATION_LLM_CALLS_PER_ANALYSIS",
    )
    remediation_llm_timeout_seconds: float = Field(
        default=45.0,
        alias="REMEDIATION_LLM_TIMEOUT_SECONDS",
    )
    remediation_stage_timeout_seconds: float = Field(
        default=90.0,
        alias="REMEDIATION_STAGE_TIMEOUT_SECONDS",
    )
    remediation_duplicate_similarity_threshold: float = Field(
        default=0.88,
        alias="REMEDIATION_DUPLICATE_SIMILARITY_THRESHOLD",
    )
    remediation_tie_epsilon: float = Field(
        default=0.02,
        alias="REMEDIATION_TIE_EPSILON",
    )
    remediation_high_risk_threshold: float = Field(
        default=0.70,
        alias="REMEDIATION_HIGH_RISK_THRESHOLD",
    )
    remediation_reject_risk_threshold: float = Field(
        default=0.90,
        alias="REMEDIATION_REJECT_RISK_THRESHOLD",
    )

    hybrid_weight_profile: str = Field(
        default="hybrid_static_v1",
        alias="HYBRID_WEIGHT_PROFILE",
    )
    min_candidate_score: float = Field(default=0.35, alias="MIN_CANDIDATE_SCORE")
    min_semantic_score: float = Field(default=0.20, alias="MIN_SEMANTIC_SCORE")
    min_history_quality_score: float = Field(
        default=0.70,
        alias="MIN_HISTORY_QUALITY_SCORE",
    )
    max_candidates_before_rerank: int = Field(
        default=30,
        alias="MAX_CANDIDATES_BEFORE_RERANK",
    )
    max_final_retrieval_results: int = Field(
        default=6,
        alias="MAX_FINAL_RETRIEVAL_RESULTS",
    )
    max_chunks_per_document: int = Field(default=2, alias="MAX_CHUNKS_PER_DOCUMENT")
    max_historical_results: int = Field(default=2, alias="MAX_HISTORICAL_RESULTS")
    diversity_lambda: float = Field(default=0.75, alias="DIVERSITY_LAMBDA")

    # Phase 5B — automated GitHub Actions ingestion (ADR-005). Disabled by default.
    # The App private key and webhook secret are environment/file values only and
    # are never returned by an API or written to a log.
    github_app_enabled: bool = Field(default=False, alias="GITHUB_APP_ENABLED")
    github_provider: Literal["github", "fake"] = Field(default="github", alias="GITHUB_PROVIDER")
    github_app_id: str = Field(default="", alias="GITHUB_APP_ID")
    github_app_slug: str = Field(default="", alias="GITHUB_APP_SLUG")
    github_app_name: str = Field(default="DevGuard AI", alias="GITHUB_APP_NAME")
    github_app_private_key_path: str = Field(default="", alias="GITHUB_APP_PRIVATE_KEY_PATH")
    github_app_private_key_pem: str = Field(default="", alias="GITHUB_APP_PRIVATE_KEY_PEM")
    github_webhook_secret: str = Field(default="", alias="GITHUB_WEBHOOK_SECRET")
    github_api_base_url: str = Field(default="https://api.github.com", alias="GITHUB_API_BASE_URL")
    github_app_install_base_url: str = Field(
        default="https://github.com/apps",
        alias="GITHUB_APP_INSTALL_BASE_URL",
    )
    github_setup_redirect_url: str = Field(
        default="http://localhost:5173/integrations/github/setup",
        alias="GITHUB_SETUP_REDIRECT_URL",
    )
    github_api_timeout_seconds: float = Field(default=20.0, alias="GITHUB_API_TIMEOUT_SECONDS")
    github_installation_token_buffer_seconds: int = Field(
        default=120,
        alias="GITHUB_INSTALLATION_TOKEN_BUFFER_SECONDS",
    )
    github_setup_state_ttl_seconds: int = Field(
        default=900,
        alias="GITHUB_SETUP_STATE_TTL_SECONDS",
    )
    github_webhook_processing_mode: Literal["background", "sync"] = Field(
        default="background",
        alias="GITHUB_WEBHOOK_PROCESSING_MODE",
    )
    github_max_delivery_attempts: int = Field(default=3, alias="GITHUB_MAX_DELIVERY_ATTEMPTS")
    github_max_log_archive_bytes: int = Field(
        default=52_428_800,
        alias="GITHUB_MAX_LOG_ARCHIVE_BYTES",
    )
    github_max_extracted_bytes: int = Field(
        default=104_857_600,
        alias="GITHUB_MAX_EXTRACTED_BYTES",
    )
    github_max_log_files: int = Field(default=25, alias="GITHUB_MAX_LOG_FILES")
    github_max_single_log_bytes: int = Field(
        default=5_242_880,
        alias="GITHUB_MAX_SINGLE_LOG_BYTES",
    )
    integration_encryption_key: str = Field(default="", alias="INTEGRATION_ENCRYPTION_KEY")

    # Phase 5C — organization invitations (link-based; SMTP deferred).
    invitation_ttl_hours: int = Field(default=168, alias="INVITATION_TTL_HOURS")
    invitation_accept_base_url: str = Field(
        default="http://localhost:5173/invitations/accept",
        alias="INVITATION_ACCEPT_BASE_URL",
    )
    frontend_public_url: str = Field(
        default="http://localhost:5173",
        alias="FRONTEND_PUBLIC_URL",
    )

    @field_validator(
        "default_budget_usd",
        "max_budget_usd_per_analysis",
        "llm_input_cost_usd_per_million_tokens",
        "llm_output_cost_usd_per_million_tokens",
        "embedding_cost_usd_per_million_tokens",
        mode="before",
    )
    @classmethod
    def empty_money_to_none(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @field_validator("embedding_batch_size", "embedding_max_input_characters", mode="after")
    @classmethod
    def positive_embedding_limits(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than zero")
        return value

    @field_validator(
        "open_set_default_confidence_threshold",
        "open_set_default_margin_threshold",
        "open_set_default_distance_threshold",
        "open_set_min_evidence_coverage",
        mode="after",
    )
    @classmethod
    def open_set_threshold_range(cls, value: float) -> float:
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError("open-set thresholds must be in [0, 1]")
        return float(value)

    @field_validator("open_set_category_thresholds_json", mode="after")
    @classmethod
    def validate_open_set_category_thresholds_json(cls, value: str) -> str:
        from app.ai.classification.open_set_detector import parse_category_thresholds_json

        parse_category_thresholds_json(value or "{}")
        return value or "{}"

    @field_validator(
        "max_causal_hypotheses",
        "min_causal_hypotheses",
        "hypothesis_graph_max_depth",
        "hypothesis_graph_max_nodes",
        "hypothesis_graph_max_edges",
        "hypothesis_max_evidence_items",
        mode="after",
    )
    @classmethod
    def positive_hypothesis_limits(cls, value: int) -> int:
        if int(value) <= 0:
            raise ValueError("hypothesis limits must be greater than zero")
        return int(value)

    @field_validator("hypothesis_duplicate_similarity_threshold", mode="after")
    @classmethod
    def hypothesis_similarity_range(cls, value: float) -> float:
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError("HYPOTHESIS_DUPLICATE_SIMILARITY_THRESHOLD must be in [0, 1]")
        return float(value)

    @field_validator(
        "max_hypotheses_for_retrieval",
        "max_queries_per_hypothesis",
        "max_results_per_query",
        "max_retrieved_items_per_hypothesis",
        "max_retrieval_context_chars",
        "max_retrieval_query_chars",
        "max_graph_context_nodes_for_retrieval",
        "max_graph_context_edges_for_retrieval",
        "max_artifact_evidence_items_for_retrieval",
        "max_historical_incidents_per_hypothesis",
        "max_concurrent_hypothesis_retrieval_sessions",
        "max_query_expansions_per_hypothesis",
        "max_follow_up_rounds",
        "max_total_queries_per_hypothesis",
        "max_source_types_per_query",
        "min_results_before_follow_up",
        "max_exact_identifiers_per_query",
        "max_retrieval_validation_items",
        "max_graph_retrieval_depth",
        "max_graph_retrieval_nodes",
        "max_graph_retrieval_edges",
        "max_artifact_results_per_query",
        "max_temporal_results_per_query",
        "max_historical_results_per_query",
        "max_official_document_results_per_query",
        "max_evidence_assessments_per_hypothesis",
        "max_candidate_hypotheses",
        "max_hypotheses_for_remediation",
        "max_remediation_candidates_per_hypothesis",
        "max_total_remediation_candidates",
        "max_constraints_per_hypothesis",
        "max_counterfactual_context_chars",
        "max_patch_characters",
        "max_patch_files_per_candidate",
        "max_changed_lines_per_candidate",
        "max_counterfactual_graph_nodes",
        "max_counterfactual_graph_edges",
        "max_assumptions_per_candidate",
        "max_expected_effects_per_candidate",
        "max_rollback_steps_per_candidate",
        "max_rule_candidates_per_hypothesis",
        "max_llm_candidates_per_hypothesis",
        "max_final_candidates_per_hypothesis",
        "max_total_final_candidates",
        "max_candidate_files",
        "max_candidate_changed_lines",
        "max_candidate_patch_characters",
        "max_candidate_explanation_characters",
        "max_candidate_assumptions",
        "max_candidate_limitations",
        "max_candidate_expected_effects",
        "max_candidate_side_effects",
        "max_candidate_risk_signals",
        "max_remediation_llm_calls_per_analysis",
        mode="after",
    )
    @classmethod
    def positive_hypothesis_retrieval_limits(cls, value: int) -> int:
        if int(value) <= 0:
            raise ValueError("hypothesis retrieval limits must be greater than zero")
        if int(value) > 100_000:
            raise ValueError("hypothesis retrieval limit exceeds safe maximum")
        return int(value)

    @field_validator("hypothesis_retrieval_timeout_seconds", mode="after")
    @classmethod
    def positive_hypothesis_retrieval_timeout(cls, value: float) -> float:
        if float(value) <= 0:
            raise ValueError("HYPOTHESIS_RETRIEVAL_TIMEOUT_SECONDS must be greater than zero")
        if float(value) > 600:
            raise ValueError("HYPOTHESIS_RETRIEVAL_TIMEOUT_SECONDS exceeds safe maximum")
        return float(value)

    @field_validator(
        "counterfactual_stage_timeout_seconds",
        "remediation_llm_timeout_seconds",
        "remediation_stage_timeout_seconds",
        mode="after",
    )
    @classmethod
    def positive_counterfactual_stage_timeout(cls, value: float) -> float:
        if float(value) <= 0:
            raise ValueError("remediation/counterfactual timeouts must be greater than zero")
        if float(value) > 600:
            raise ValueError("remediation/counterfactual timeout exceeds safe maximum")
        return float(value)

    @field_validator("max_retrieval_total_duration_seconds", mode="after")
    @classmethod
    def positive_retrieval_total_duration(cls, value: float) -> float:
        if float(value) <= 0:
            raise ValueError("MAX_RETRIEVAL_TOTAL_DURATION_SECONDS must be greater than zero")
        if float(value) > 600:
            raise ValueError("MAX_RETRIEVAL_TOTAL_DURATION_SECONDS exceeds safe maximum")
        return float(value)

    @field_validator("min_retrieval_score_for_acceptance", mode="after")
    @classmethod
    def retrieval_acceptance_score_bounds(cls, value: float) -> float:
        score = float(value)
        if score < 0.0 or score > 1.0:
            raise ValueError("MIN_RETRIEVAL_SCORE_FOR_ACCEPTANCE must be in [0, 1]")
        return score

    @field_validator(
        "min_ranking_score_for_top_candidate",
        "ranking_tie_epsilon",
        "remediation_duplicate_similarity_threshold",
        "remediation_tie_epsilon",
        "remediation_high_risk_threshold",
        "remediation_reject_risk_threshold",
        mode="after",
    )
    @classmethod
    def evidence_assessment_score_bounds(cls, value: float) -> float:
        score = float(value)
        if score < 0.0 or score > 1.0:
            raise ValueError("evidence assessment / remediation scores must be in [0, 1]")
        return score

    @field_validator("embedding_model", mode="after")
    @classmethod
    def embedding_model_when_sentence_transformers(cls, value: str, info) -> str:
        model = (value or "").strip()
        provider = info.data.get("embedding_provider")
        if provider == "sentence_transformers" and not model:
            raise ValueError(
                "EMBEDDING_MODEL must not be empty when EMBEDDING_PROVIDER=sentence_transformers"
            )
        return model or "sentence-transformers/all-MiniLM-L6-v2"

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return ["http://localhost:5173"]

    @field_validator("database_url", mode="after")
    @classmethod
    def assemble_database_url(cls, value: str | None, info) -> str:
        if value:
            return value
        data = info.data
        return (
            f"postgresql+asyncpg://{data['postgres_user']}:"
            f"{data['postgres_password']}@"
            f"{data['postgres_host']}:"
            f"{data['postgres_port']}/"
            f"{data['postgres_db']}"
        )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def validate_for_runtime(self) -> list[str]:
        """Return configuration problems. Production raises on unsafe values."""
        problems: list[str] = []
        if len(self.jwt_secret_key or "") < 32:
            problems.append("JWT_SECRET_KEY must be at least 32 characters")
        if self.max_upload_size_bytes <= 0:
            problems.append("MAX_UPLOAD_SIZE_BYTES must be > 0")
        if self.max_files_per_upload <= 0:
            problems.append("MAX_FILES_PER_UPLOAD must be > 0")
        if self.openai_timeout_seconds <= 0:
            problems.append("OPENAI_TIMEOUT_SECONDS must be > 0")
        if self.openai_max_retries < 0:
            problems.append("OPENAI_MAX_RETRIES must be >= 0")
        if self.openai_retry_base_delay_ms <= 0 or self.openai_retry_max_delay_ms <= 0:
            problems.append("OpenAI retry delay settings must be > 0")
        if (
            self.llm_input_cost_usd_per_million_tokens is not None
            and self.llm_input_cost_usd_per_million_tokens < 0
        ):
            problems.append("OPENAI/LLM input cost must be >= 0")
        if (
            self.llm_output_cost_usd_per_million_tokens is not None
            and self.llm_output_cost_usd_per_million_tokens < 0
        ):
            problems.append("OPENAI/LLM output cost must be >= 0")
        if (
            self.max_concurrent_hypothesis_retrieval_sessions
            > self.max_hypotheses_for_retrieval
        ):
            problems.append(
                "MAX_CONCURRENT_HYPOTHESIS_RETRIEVAL_SESSIONS cannot exceed "
                "MAX_HYPOTHESES_FOR_RETRIEVAL"
            )
        if self.max_follow_up_rounds > 2:
            problems.append("MAX_FOLLOW_UP_ROUNDS cannot exceed 2")
        if self.max_total_queries_per_hypothesis < self.max_queries_per_hypothesis:
            problems.append(
                "MAX_TOTAL_QUERIES_PER_HYPOTHESIS must be >= MAX_QUERIES_PER_HYPOTHESIS"
            )
        if (
            self.max_total_remediation_candidates
            < self.max_remediation_candidates_per_hypothesis
        ):
            problems.append(
                "MAX_TOTAL_REMEDIATION_CANDIDATES must be >= "
                "MAX_REMEDIATION_CANDIDATES_PER_HYPOTHESIS"
            )
        if self.max_hypotheses_for_remediation > 20:
            problems.append("MAX_HYPOTHESES_FOR_REMEDIATION exceeds safe maximum (20)")
        if self.max_changed_lines_per_candidate > self.max_patch_characters:
            problems.append(
                "MAX_CHANGED_LINES_PER_CANDIDATE is inconsistent with MAX_PATCH_CHARACTERS"
            )
        if self.max_patch_files_per_candidate > 50:
            problems.append("MAX_PATCH_FILES_PER_CANDIDATE exceeds safe maximum (50)")
        if self.max_total_final_candidates < self.max_final_candidates_per_hypothesis:
            problems.append(
                "MAX_TOTAL_FINAL_CANDIDATES must be >= MAX_FINAL_CANDIDATES_PER_HYPOTHESIS"
            )
        if self.max_final_candidates_per_hypothesis < self.max_rule_candidates_per_hypothesis:
            problems.append(
                "MAX_FINAL_CANDIDATES_PER_HYPOTHESIS should be >= "
                "MAX_RULE_CANDIDATES_PER_HYPOTHESIS"
            )
        if self.max_candidate_changed_lines > self.max_candidate_patch_characters:
            problems.append(
                "MAX_CANDIDATE_CHANGED_LINES is inconsistent with "
                "MAX_CANDIDATE_PATCH_CHARACTERS"
            )
        if self.remediation_reject_risk_threshold < self.remediation_high_risk_threshold:
            problems.append(
                "REMEDIATION_REJECT_RISK_THRESHOLD must be >= "
                "REMEDIATION_HIGH_RISK_THRESHOLD"
            )
        if self.max_remediation_llm_calls_per_analysis > 20:
            problems.append("MAX_REMEDIATION_LLM_CALLS_PER_ANALYSIS exceeds safe maximum (20)")
        problems.extend(self._github_problems())
        if self.is_production:
            if self.debug:
                problems.append("DEBUG must be false in production")
            if self.bootstrap_enabled:
                problems.append("BOOTSTRAP_ENABLED must be false in production")
            if not self.backend_cors_origins:
                problems.append("BACKEND_CORS_ORIGINS must be set in production")
            if self.postgres_password in {"", "change_me"}:
                problems.append("POSTGRES_PASSWORD must not use development default")
            if (
                self.enable_external_llm
                and self.llm_provider == "openai"
                and not self.openai_api_key
            ):
                problems.append("OPENAI_API_KEY required when external OpenAI is enabled")
            if self.rag_backend == "chroma" and not (self.chroma_host or self.chroma_persist_path):
                problems.append("Chroma requires CHROMA_HOST or CHROMA_PERSIST_PATH")
            if self.github_app_enabled and not self.integration_encryption_key:
                problems.append("INTEGRATION_ENCRYPTION_KEY required when GITHUB_APP_ENABLED=true")
            if self.github_provider == "fake":
                problems.append("GITHUB_PROVIDER=fake must not be used in production")
        return problems

    def _github_problems(self) -> list[str]:
        """GitHub App configuration requirements when ingestion is enabled.

        Credentials for the real GitHub API are only required when the real
        provider is selected; the deterministic fake provider used by tests
        still requires a webhook secret so signature validation stays exercised.
        """
        if not self.github_app_enabled:
            return []
        problems: list[str] = []
        if not self.github_webhook_secret:
            problems.append("GITHUB_WEBHOOK_SECRET is required when GITHUB_APP_ENABLED=true")
        if self.github_provider == "github":
            if not self.github_app_id:
                problems.append("GITHUB_APP_ID is required when GITHUB_APP_ENABLED=true")
            if not (self.github_app_private_key_path or self.github_app_private_key_pem):
                problems.append(
                    "GITHUB_APP_PRIVATE_KEY_PATH or GITHUB_APP_PRIVATE_KEY_PEM is required "
                    "when GITHUB_APP_ENABLED=true"
                )
        if self.github_max_log_archive_bytes <= 0 or self.github_max_extracted_bytes <= 0:
            problems.append("GitHub log archive size limits must be > 0")
        if self.github_max_log_files <= 0:
            problems.append("GITHUB_MAX_LOG_FILES must be > 0")
        return problems


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    settings = Settings()
    problems = settings.validate_for_runtime()
    if settings.is_production and problems:
        raise ValueError("Unsafe production configuration: " + "; ".join(problems))
    return settings
