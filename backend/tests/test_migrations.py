"""Alembic lifecycle tests against disposable PostgreSQL."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import Settings

EXPECTED_TABLES = {
    "activation_challenges",
    "alembic_version",
    "audit_events",
    "auth_sessions",
    "bootstrap_state",
    "finance_categories",
    "financial_events",
    "ownership_transfers",
    "recovery_challenges",
    "user_accounts",
    "workspaces",
    "workspace_memberships",
    "workspace_modules",
}

FOUNDATION_TABLES = EXPECTED_TABLES - {
    "activation_challenges",
    "audit_events",
    "auth_sessions",
    "ownership_transfers",
    "recovery_challenges",
    "finance_categories",
    "financial_events",
}

PHASE_ONE_TABLES = EXPECTED_TABLES - {"finance_categories", "financial_events"}


@pytest.mark.postgres
def test_clean_upgrade_and_downgrade(database_settings: Settings) -> None:
    """All revisions upgrade cleanly, create only scoped tables, and roll back."""
    configuration = Config(Path(__file__).parents[1] / "alembic.ini")
    sync_url = database_settings.database_url.set(drivername="postgresql+psycopg")
    engine = create_engine(sync_url)
    try:
        command.downgrade(configuration, "base")
        command.upgrade(configuration, "head")
        assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES

        command.downgrade(configuration, "base")
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}

        command.upgrade(configuration, "head")
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_incremental_upgrade_from_identity_foundation(database_settings: Settings) -> None:
    """The second revision upgrades an existing Issue #43 database without a rebuild."""
    configuration = Config(Path(__file__).parents[1] / "alembic.ini")
    sync_url = database_settings.database_url.set(drivername="postgresql+psycopg")
    engine = create_engine(sync_url)
    try:
        command.downgrade(configuration, "20260809_0001")
        assert set(inspect(engine).get_table_names()) == FOUNDATION_TABLES

        command.upgrade(configuration, "head")
        assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
    finally:
        engine.dispose()


@pytest.mark.postgres
def test_incremental_upgrade_from_phase_one_head(database_settings: Settings) -> None:
    """Issue #79 upgrades and downgrades the representative Phase 1 head in place."""
    configuration = Config(Path(__file__).parents[1] / "alembic.ini")
    sync_url = database_settings.database_url.set(drivername="postgresql+psycopg")
    engine = create_engine(sync_url)
    try:
        command.downgrade(configuration, "20260809_0002")
        assert set(inspect(engine).get_table_names()) == PHASE_ONE_TABLES

        command.upgrade(configuration, "head")
        assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
    finally:
        engine.dispose()
