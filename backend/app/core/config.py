"""Application configuration via Pydantic Settings."""

import json
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
