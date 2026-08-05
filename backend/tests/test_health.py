"""Application factory and liveness contract tests."""

from fastapi.testclient import TestClient

from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app


def test_liveness_returns_only_non_sensitive_status() -> None:
    """The liveness contract reveals no configuration or dependency data."""
    settings = Settings(
        environment=RuntimeEnvironment.TEST,
        debug=False,
        docs_enabled=False,
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_documentation_is_disabled_by_default() -> None:
    """The factory does not expose documentation without explicit opt-in."""
    settings = Settings(
        environment=RuntimeEnvironment.TEST,
        debug=False,
        docs_enabled=False,
    )

    with TestClient(create_app(settings)) as client:
        docs_response = client.get("/docs")
        schema_response = client.get("/openapi.json")

    assert docs_response.status_code == 404
    assert schema_response.status_code == 404


def test_local_documentation_can_be_enabled_explicitly() -> None:
    """Local development can opt in without weakening production rules."""
    settings = Settings(
        environment=RuntimeEnvironment.LOCAL,
        debug=False,
        docs_enabled=True,
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "F2S API"
