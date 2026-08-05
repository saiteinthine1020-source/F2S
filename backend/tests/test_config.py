"""Runtime configuration safety tests."""

import pytest
from pydantic import ValidationError

from app.core.config import RuntimeEnvironment, Settings


def test_defaults_are_non_debug_local_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default startup exposes no debug or documentation surface."""
    for variable in ("F2S_ENVIRONMENT", "F2S_DEBUG", "F2S_DOCS_ENABLED"):
        monkeypatch.delenv(variable, raising=False)

    settings = Settings()

    assert settings.environment is RuntimeEnvironment.LOCAL
    assert settings.debug is False
    assert settings.docs_enabled is False


@pytest.mark.parametrize("unsafe_field", ["debug", "docs_enabled"])
def test_production_rejects_unsafe_surfaces(unsafe_field: str) -> None:
    """Production configuration fails closed for unsafe surfaces."""
    values: dict[str, object] = {
        "environment": RuntimeEnvironment.PRODUCTION,
        unsafe_field: True,
    }

    with pytest.raises(ValidationError):
        Settings.model_validate(values)


def test_unknown_environment_is_rejected() -> None:
    """Unsupported environment names cannot start the application."""
    with pytest.raises(ValidationError):
        Settings.model_validate({"environment": "staging"})


def test_unknown_setting_is_rejected() -> None:
    """Mistyped or unowned settings fail instead of being ignored."""
    with pytest.raises(ValidationError):
        Settings.model_validate({"unknown_setting": True})
