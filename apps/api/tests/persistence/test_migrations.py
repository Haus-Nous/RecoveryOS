"""Automated Alembic migration upgrade, downgrade, and re-upgrade test."""

import os

from alembic.config import Config

from alembic import command


def test_alembic_upgrade_downgrade_cycle() -> None:
    """Verify that Alembic migrations cleanly downgrade to base and upgrade to head."""
    app_env = os.environ.get("APP_ENV", "test").lower()
    if app_env in ("production", "prod", "staging", "stage"):
        raise RuntimeError(f"ABORTING destructive migration test: APP_ENV is set to '{app_env}'!")

    api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    alembic_ini = os.path.join(api_dir, "alembic.ini")
    config = Config(alembic_ini)
    config.set_main_option("script_location", os.path.join(api_dir, "alembic"))
    config.set_main_option(
        "sqlalchemy.url",
        os.environ.get(
            "SYNC_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/recoveryos"
        ),
    )

    # 1. Downgrade to base
    command.downgrade(config, "base")

    # 2. Upgrade to head
    command.upgrade(config, "head")

    # 3. Re-verify downgrade to base
    command.downgrade(config, "base")

    # 4. Final upgrade to head
    command.upgrade(config, "head")
