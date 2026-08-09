"""Runtime configuration safety tests."""

import pytest
from pydantic import ValidationError

from app.core.config import DatabaseSslMode, RuntimeEnvironment, Settings

DATABASE_VALUES: dict[str, object] = {
    "database_host": "127.0.0.1",
    "database_name": "f2s_test",
    "database_user": "f2s_test_owner",
    "database_password": "-".join(("synthetic", "test", "value")),
    "identity_digest_key": "-".join(("synthetic", "identity", "digest", "key", "material", "only")),
}


def test_defaults_are_non_debug_local_settings() -> None:
    """Default surfaces stay disabled when database settings are supplied."""
    settings = Settings.model_validate({**DATABASE_VALUES, "environment": "local"})

    assert settings.environment is RuntimeEnvironment.LOCAL
    assert settings.debug is False
    assert settings.docs_enabled is False


@pytest.mark.parametrize("unsafe_field", ["debug", "docs_enabled"])
def test_production_rejects_unsafe_surfaces(unsafe_field: str) -> None:
    """Production configuration fails closed for unsafe surfaces."""
    values: dict[str, object] = {
        **DATABASE_VALUES,
        "environment": RuntimeEnvironment.PRODUCTION,
        "database_sslmode": DatabaseSslMode.VERIFY_FULL,
        unsafe_field: True,
    }

    with pytest.raises(ValidationError):
        Settings.model_validate(values)


def test_unknown_environment_is_rejected() -> None:
    """Unsupported environment names cannot start the application."""
    with pytest.raises(ValidationError):
        Settings.model_validate({**DATABASE_VALUES, "environment": "staging"})


def test_unknown_setting_is_rejected() -> None:
    """Mistyped or unowned settings fail instead of being ignored."""
    with pytest.raises(ValidationError):
        Settings.model_validate({**DATABASE_VALUES, "unknown_setting": True})


def test_database_configuration_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Startup fails closed when a required connection field is absent."""
    values = DATABASE_VALUES.copy()
    del values["database_name"]
    monkeypatch.delenv("F2S_DATABASE_NAME")

    with pytest.raises(ValidationError):
        Settings.model_validate(values)


def test_production_requires_verified_database_tls() -> None:
    """Production refuses an encrypted-but-unverified database connection."""
    with pytest.raises(ValidationError):
        Settings.model_validate({**DATABASE_VALUES, "environment": "production"})


def test_database_secret_is_redacted() -> None:
    """Settings and URL representations do not reveal the database password."""
    settings = Settings.model_validate(DATABASE_VALUES)
    password = str(DATABASE_VALUES["database_password"])

    assert password not in repr(settings)
    assert password not in settings.database_url.render_as_string()
    assert settings.database_url.drivername == "postgresql+psycopg"
    assert settings.identity_digest_key.get_secret_value() not in repr(settings)


def test_short_identity_digest_key_is_rejected() -> None:
    values = {**DATABASE_VALUES, "identity_digest_key": "too-short"}
    with pytest.raises(ValidationError):
        Settings.model_validate(values)
