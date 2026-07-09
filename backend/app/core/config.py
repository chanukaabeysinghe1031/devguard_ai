"""Application configuration via environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="DevGuard AI", alias="APP_NAME")
    app_env: Literal["development", "staging", "production"] = Field(
        default="development", alias="APP_ENV"
    )
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    app_secret_key: str = Field(
        default="dev-only-change-me-before-production-min-32-chars",
        alias="APP_SECRET_KEY",
        min_length=32,
    )
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")

    # Server
    backend_host: str = Field(default="0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        alias="CORS_ORIGINS",
    )

    # Database
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_user: str = Field(default="devguard", alias="POSTGRES_USER")
    postgres_password: str = Field(default="devguard_secret", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="devguard_ai", alias="POSTGRES_DB")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    # ChromaDB
    chroma_host: str = Field(default="localhost", alias="CHROMA_HOST")
    chroma_port: int = Field(default=8001, alias="CHROMA_PORT")
    chroma_persist_dir: str = Field(default="./backend/data/chroma", alias="CHROMA_PERSIST_DIR")

    # OpenAI
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL"
    )

    # ML
    ml_model_dir: str = Field(default="./backend/data/models", alias="ML_MODEL_DIR")
    ml_default_classifier: str = Field(
        default="logistic_regression", alias="ML_DEFAULT_CLASSIFIER"
    )

    # Upload
    max_upload_size_mb: int = Field(default=50, alias="MAX_UPLOAD_SIZE_MB")
    allowed_log_extensions: str = Field(default=".log,.txt", alias="ALLOWED_LOG_EXTENSIONS")
    allowed_config_extensions: str = Field(
        default=".yml,.yaml,.tf,.hcl,.json", alias="ALLOWED_CONFIG_EXTENSIONS"
    )

    # Security
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: Literal["json", "console"] = Field(default="json", alias="LOG_FORMAT")

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
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_log_ext_set(self) -> set[str]:
        return {ext.strip().lower() for ext in self.allowed_log_extensions.split(",")}

    @property
    def allowed_config_ext_set(self) -> set[str]:
        return {ext.strip().lower() for ext in self.allowed_config_extensions.split(",")}

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton for dependency injection."""
    return Settings()
