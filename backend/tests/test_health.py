"""Application factory and liveness contract tests."""

from fastapi import APIRouter
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
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Content-Security-Policy"].startswith("default-src 'none'")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" not in response.headers


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


def test_untrusted_host_is_rejected() -> None:
    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    with TestClient(create_app(settings)) as client:
        response = client.get("/health/live", headers={"Host": "hostile.example"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_HOST"
    assert response.headers["Cache-Control"] == "no-store"


def test_unexpected_exception_is_concealed() -> None:
    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    application = create_app(settings)
    router = APIRouter()

    @router.get("/api/v1/synthetic-failure")
    async def synthetic_failure() -> None:
        raise RuntimeError("synthetic-sensitive-exception-canary")

    application.include_router(router)
    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/synthetic-failure")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "synthetic-sensitive-exception-canary" not in response.text
    assert response.headers["Cache-Control"] == "no-store"


def test_production_responses_include_hsts() -> None:
    settings = Settings(
        environment=RuntimeEnvironment.PRODUCTION,
        debug=False,
        docs_enabled=False,
        database_host="postgres.internal",
        database_name="f2s",
        database_user="f2s_owner",
        database_password="G7v!p9R2x#K4mQ8zL1wC",
        database_sslmode="verify-full",
        identity_digest_key="ci-verification-key-material-" + ("k" * 32),
        frontend_origin="https://app.f2s.example",
        api_allowed_hosts=("api.f2s.example",),
    )
    with TestClient(create_app(settings), base_url="https://api.f2s.example") as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000"
