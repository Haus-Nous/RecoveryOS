"""Automated Alembic migration upgrade, downgrade, and re-upgrade test."""

import os

from alembic.config import Config

from alembic import command


def assert_safe_test_database(db_url: str, app_env: str) -> None:
    """Fail-closed assertion ensuring destructive operations execute ONLY on test databases.

    Rules:
    1. APP_ENV must equal 'test'.
    2. Database name in db_url must end with '_test'.
    3. Production, staging, and development environments are strictly blocked.
    """
    normalized_env = app_env.strip().lower()
    if normalized_env != "test":
        raise RuntimeError(
            f"DESTRUCTIVE DB TEST BLOCKED: APP_ENV is '{normalized_env}', expected 'test'."
        )

    # Extract db name from database URL (stripping query parameters if any)
    path = db_url.split("?")[0].rstrip("/")
    db_name = path.split("/")[-1]

    if not db_name.endswith("_test"):
        raise RuntimeError(
            f"DESTRUCTIVE DB TEST BLOCKED: Database '{db_name}' does not end with '_test'."
        )


def test_destructive_guard_rejects_unsafe_configurations() -> None:
    """Verify that the destructive operation guard fails closed on all non-test configurations."""
    import pytest

    # 1. Rejects non-test APP_ENV
    with pytest.raises(RuntimeError, match="APP_ENV is 'production'"):
        assert_safe_test_database(
            "postgresql://postgres:postgres@localhost:5432/recoveryos_test", "production"
        )

    with pytest.raises(RuntimeError, match="APP_ENV is 'staging'"):
        assert_safe_test_database(
            "postgresql://postgres:postgres@localhost:5432/recoveryos_test", "staging"
        )

    with pytest.raises(RuntimeError, match="APP_ENV is 'development'"):
        assert_safe_test_database(
            "postgresql://postgres:postgres@localhost:5432/recoveryos_test", "development"
        )

    # 2. Rejects non-test database names even if APP_ENV == test
    with pytest.raises(RuntimeError, match="does not end with '_test'"):
        assert_safe_test_database(
            "postgresql://postgres:postgres@localhost:5432/recoveryos", "test"
        )

    with pytest.raises(RuntimeError, match="does not end with '_test'"):
        assert_safe_test_database(
            "postgresql://postgres:postgres@localhost:5432/recoveryos_prod", "test"
        )

    # 3. Accepts valid test configuration
    assert_safe_test_database(
        "postgresql://postgres:postgres@localhost:5432/recoveryos_test", "test"
    )
    assert_safe_test_database(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/recoveryos_test?ssl=require", "test"
    )


def test_alembic_upgrade_downgrade_cycle() -> None:
    """Verify that Alembic migrations cleanly downgrade to base and upgrade to head."""
    app_env = os.environ.get("APP_ENV", "test")
    db_url = os.environ.get(
        "SYNC_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/recoveryos_test"
    )

    # Enforce fail-closed guard before destructive migration cycle
    assert_safe_test_database(db_url, app_env)

    api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    alembic_ini = os.path.join(api_dir, "alembic.ini")
    config = Config(alembic_ini)
    config.set_main_option("script_location", os.path.join(api_dir, "alembic"))
    config.set_main_option("sqlalchemy.url", db_url)

    # 1. Downgrade to base
    command.downgrade(config, "base")

    # 2. Upgrade to head
    command.upgrade(config, "head")

    # 3. Re-verify downgrade to base
    command.downgrade(config, "base")

    # 4. Final upgrade to head
    command.upgrade(config, "head")


def test_alembic_downgrade_0001_and_check() -> None:
    """Verify specific downgrade from 0002 to 0001 and ensure alembic check reports no drift."""
    app_env = os.environ.get("APP_ENV", "test")
    db_url = os.environ.get(
        "SYNC_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/recoveryos_test"
    )

    assert_safe_test_database(db_url, app_env)

    api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    alembic_ini = os.path.join(api_dir, "alembic.ini")
    config = Config(alembic_ini)
    config.set_main_option("script_location", os.path.join(api_dir, "alembic"))
    config.set_main_option("sqlalchemy.url", db_url)

    # 1. Downgrade to revision 0001_initial_financial_schema
    command.downgrade(config, "0001_initial_financial_schema")

    # 2. Re-upgrade to head
    command.upgrade(config, "head")

    # 3. Alembic check for schema model consistency
    command.check(config)


def test_alembic_downgrade_0002_and_check() -> None:
    """Verify specific downgrade from 0003 to 0002 and re-upgrade to head with zero schema drift."""
    app_env = os.environ.get("APP_ENV", "test")
    db_url = os.environ.get(
        "SYNC_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/recoveryos_test"
    )

    assert_safe_test_database(db_url, app_env)

    api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    alembic_ini = os.path.join(api_dir, "alembic.ini")
    config = Config(alembic_ini)
    config.set_main_option("script_location", os.path.join(api_dir, "alembic"))
    config.set_main_option("sqlalchemy.url", db_url)

    # 1. Downgrade to revision 0002_identity_and_membership
    command.downgrade(config, "0002_identity_and_membership")

    # 2. Re-upgrade to head (0003_provider_connections)
    command.upgrade(config, "head")

    # 3. Alembic check for schema model consistency
    command.check(config)
