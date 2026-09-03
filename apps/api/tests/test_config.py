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
