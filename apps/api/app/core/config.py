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

    # Authentication / OIDC / Supabase
    auth_issuer: str | None = None
    auth_audience: str | None = "authenticated"
    auth_jwks_url: str | None = None
    auth_allowed_algorithms: list[str] = ["ES256", "RS256"]
    auth_jwks_cache_ttl_seconds: int = 300
    auth_clock_skew_seconds: int = 10

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse comma-separated origins string into list of trimmed strings."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return [str(origin).strip() for origin in v if str(origin).strip()]
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("auth_allowed_algorithms", mode="before")
    @classmethod
    def parse_auth_algorithms(cls, v: Any) -> list[str]:
        """Parse comma-separated algorithms string into list of uppercase strings."""
        if isinstance(v, str):
            return [alg.strip().upper() for alg in v.split(",") if alg.strip()]
        if isinstance(v, list):
            return [str(alg).strip().upper() for alg in v if str(alg).strip()]
        return ["ES256", "RS256"]

    def validate_production_auth_config(self) -> None:
        """Fail-closed assertion ensuring staging and production require valid asymmetric auth config."""
        env = self.app_env.strip().lower()
        if env in ("production", "staging"):
            if not self.auth_issuer:
                raise ValueError(
                    f"FAIL-CLOSED CONFIG ERROR: 'AUTH_ISSUER' is mandatory in [{env}] environment."
                )
            if not self.auth_jwks_url:
                raise ValueError(
                    f"FAIL-CLOSED CONFIG ERROR: 'AUTH_JWKS_URL' is mandatory in [{env}] environment."
                )
            disallowed = [
                alg
                for alg in self.auth_allowed_algorithms
                if alg in ("NONE", "HS256", "HS384", "HS512")
            ]
            if disallowed:
                raise ValueError(
                    f"FAIL-CLOSED CONFIG ERROR: Symmetric or insecure algorithms {disallowed} are forbidden in [{env}]."
                )

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
    """Return cached instance of Settings and validate production fail-closed invariants."""
    settings = Settings()
    settings.validate_production_auth_config()
    return settings
