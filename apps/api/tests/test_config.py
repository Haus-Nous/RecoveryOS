"""Tests for Settings and configuration management."""

from app.core.config import Settings


def test_settings_defaults() -> None:
    """Settings instantiate with safe default development values."""
    settings = Settings(
        app_env="local",
        api_port=8000,
        cors_allowed_origins="http://localhost:3000,http://127.0.0.1:3000",
    )
    assert settings.app_name == "RecoveryOS API"
    assert settings.app_env == "local"
    assert not settings.is_production
    assert not settings.is_testing
    assert len(settings.cors_allowed_origins) == 2
    assert "http://localhost:3000" in settings.cors_allowed_origins


def test_cors_origin_parsing() -> None:
    """CORS origins should handle comma separated strings and lists cleanly."""
    settings_str = Settings(
        cors_allowed_origins="https://app.recoveryos.com, https://admin.recoveryos.com"
    )
    assert settings_str.cors_allowed_origins == [
        "https://app.recoveryos.com",
        "https://admin.recoveryos.com",
    ]

    settings_list = Settings(cors_allowed_origins=["https://test.recoveryos.com"])
    assert settings_list.cors_allowed_origins == ["https://test.recoveryos.com"]


def test_production_auth_config_fail_closed() -> None:
    """Production and staging must fail closed if auth configuration is incomplete or insecure."""
    import pytest

    # 1. Missing issuer in production
    settings_missing_issuer = Settings(
        app_env="production",
        auth_issuer=None,
        auth_audience="authenticated",
        auth_jwks_url="https://auth.example.com/.well-known/jwks.json",
    )
    with pytest.raises(ValueError, match="AUTH_ISSUER"):
        settings_missing_issuer.validate_production_auth_config()

    # 2. Missing audience in staging
    settings_missing_audience = Settings(
        app_env="staging",
        auth_issuer="https://auth.example.com",
        auth_audience=None,
        auth_jwks_url="https://auth.example.com/.well-known/jwks.json",
    )
    with pytest.raises(ValueError, match="AUTH_AUDIENCE"):
        settings_missing_audience.validate_production_auth_config()

    # 3. Missing jwks_url in production
    settings_missing_jwks = Settings(
        app_env="production",
        auth_issuer="https://auth.example.com",
        auth_audience="authenticated",
        auth_jwks_url=None,
    )
    with pytest.raises(ValueError, match="AUTH_JWKS_URL"):
        settings_missing_jwks.validate_production_auth_config()

    # 4. Insecure algorithms in production
    settings_insecure_alg = Settings(
        app_env="production",
        auth_issuer="https://auth.example.com",
        auth_audience="authenticated",
        auth_jwks_url="https://auth.example.com/.well-known/jwks.json",
        auth_allowed_algorithms=["HS256", "ES256"],
    )
    with pytest.raises(ValueError, match="Symmetric or insecure algorithms"):
        settings_insecure_alg.validate_production_auth_config()

    # 5. Valid asymmetric config passes
    valid_settings = Settings(
        app_env="production",
        auth_issuer="https://auth.example.com",
        auth_audience="authenticated",
        auth_jwks_url="https://auth.example.com/.well-known/jwks.json",
        auth_allowed_algorithms=["ES256", "RS256"],
    )
    valid_settings.validate_production_auth_config()
