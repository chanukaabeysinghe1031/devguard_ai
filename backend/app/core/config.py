"""Application configuration via Pydantic Settings."""

import json
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, field_validator
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
    llm_provider: Literal["local", "openai"] = Field(default="local", alias="LLM_PROVIDER")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    chroma_persist_path: str = Field(default="./storage/chroma", alias="CHROMA_PERSIST_PATH")
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
        alias="LLM_INPUT_COST_USD_PER_MILLION_TOKENS",
    )
    llm_output_cost_usd_per_million_tokens: Decimal | None = Field(
        default=None,
        alias="LLM_OUTPUT_COST_USD_PER_MILLION_TOKENS",
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


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
