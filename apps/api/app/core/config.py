"""Centralized application settings powered by Pydantic Settings."""

from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RecoveryOS API"
    app_env: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "info"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/recoveryos"
    sync_database_url: str = "postgresql://postgres:postgres@localhost:5432/recoveryos"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # CORS
    cors_allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse comma-separated origins string into list of trimmed strings."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return [str(origin).strip() for origin in v if str(origin).strip()]
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def is_production(self) -> bool:
        """Check if current environment is production."""
        return self.app_env.lower() == "production"

    @property
    def is_testing(self) -> bool:
        """Check if current environment is testing."""
        return self.app_env.lower() == "test"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached instance of Settings."""
    return Settings()
