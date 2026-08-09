"""Alembic lifecycle tests against disposable PostgreSQL."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import Settings

EXPECTED_TABLES = {
    "alembic_version",
    "bootstrap_state",
    "user_accounts",
    "workspaces",
    "workspace_memberships",
    "workspace_modules",
}


@pytest.mark.postgres
def test_clean_upgrade_and_downgrade(database_settings: Settings) -> None:
    """The first revision upgrades cleanly, creates only scoped tables, and rolls back."""
    configuration = Config(Path(__file__).parents[1] / "alembic.ini")
    sync_url = database_settings.database_url.set(drivername="postgresql+psycopg")
    engine = create_engine(sync_url)
    try:
        command.downgrade(configuration, "base")
        command.upgrade(configuration, "head")
        assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES

        command.downgrade(configuration, "base")
        assert inspect(engine).get_table_names() == []

        command.upgrade(configuration, "head")
    finally:
        engine.dispose()
