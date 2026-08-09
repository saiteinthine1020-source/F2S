"""Shared test configuration and PostgreSQL integration fixtures."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.core.config import Settings

_SYNTHETIC_PASSWORD = "-".join(("synthetic", "test", "value"))
_SYNTHETIC_DIGEST_KEY = "-".join(("synthetic", "identity", "digest", "key", "material", "only"))
_TEST_ENVIRONMENT = {
    "F2S_ENVIRONMENT": "test",
    "F2S_DATABASE_HOST": "127.0.0.1",
    "F2S_DATABASE_PORT": "5432",
    "F2S_DATABASE_NAME": "f2s_test",
    "F2S_DATABASE_USER": "f2s_test_owner",
    "F2S_DATABASE_PASSWORD": _SYNTHETIC_PASSWORD,
    "F2S_DATABASE_SSLMODE": "disable",
    "F2S_IDENTITY_DIGEST_KEY": _SYNTHETIC_DIGEST_KEY,
}
for _name, _value in _TEST_ENVIRONMENT.items():
    os.environ.setdefault(_name, _value)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip explicit PostgreSQL tests unless their isolated database is enabled."""
    if os.environ.get("F2S_RUN_POSTGRES_TESTS") == "1":
        return
    marker = pytest.mark.skip(reason="set F2S_RUN_POSTGRES_TESTS=1 with a disposable PostgreSQL")
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(marker)


@pytest.fixture(scope="session")
def database_settings() -> Settings:
    """Return validated integration database settings."""
    return Settings()


@pytest.fixture(scope="session")
def migrated_database(database_settings: Settings) -> Iterator[Settings]:
    """Upgrade the disposable database and restore it to base after the session."""
    configuration = Config(Path(__file__).parents[1] / "alembic.ini")
    command.upgrade(configuration, "head")
    yield database_settings
    command.downgrade(configuration, "base")
