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

    @field_validator("embedding_batch_size", "embedding_max_input_characters", mode="after")
    @classmethod
    def positive_embedding_limits(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than zero")
        return value

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
        return problems


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    settings = Settings()
    problems = settings.validate_for_runtime()
    if settings.is_production and problems:
        raise ValueError("Unsafe production configuration: " + "; ".join(problems))
    return settings
