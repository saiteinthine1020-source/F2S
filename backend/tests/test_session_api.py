"""Browser origin, cookie, CSRF, and session response API tests."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app
from app.modules.identity_security import DevelopmentSubjectAbuseControl, SecretText
from app.modules.sessions import SessionTokens


class StubSessionService:
    def __init__(self, tokens: SessionTokens | None) -> None:
        self.tokens = tokens

    async def login(self, attempt: object) -> SessionTokens | None:
        del attempt
        return self.tokens

    async def rotate(self, attempt: object) -> SessionTokens | None:
        del attempt
        return self.tokens

    async def logout(self, attempt: object) -> None:
        del attempt


def _tokens() -> SessionTokens:
    now = datetime.now(UTC)
    return SessionTokens(
        access=SecretText("synthetic-access-credential-value-not-persisted"),
        refresh=SecretText("synthetic-refresh-credential-value-not-persisted"),
        csrf=SecretText("synthetic-csrf-credential-value-not-persisted"),
        access_expires_at=now + timedelta(minutes=15),
        refresh_expires_at=now + timedelta(days=7),
        absolute_expires_at=now + timedelta(days=30),
    )


def test_login_sets_host_cookie_and_returns_no_refresh_value(monkeypatch: object) -> None:
    from app.api import sessions as session_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    tokens = _tokens()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        session_api,
        "service_for",
        lambda request, session: StubSessionService(tokens),
    )
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        response = client.post(
            "/api/v1/auth/login",
            headers={"Origin": settings.frontend_origin},
            json={
                "email": "member@example.invalid",
                "password": "synthetic-valid-password",
            },
        )

    cookie = response.headers["set-cookie"]
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Access-Control-Allow-Origin"] == settings.frontend_origin
    assert tokens.access.reveal() in response.text
    assert tokens.csrf.reveal() in response.text
    assert tokens.refresh.reveal() not in response.text
    assert cookie.startswith("__Host-f2s_refresh=")
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
    assert "Domain=" not in cookie


def test_login_rejects_hostile_or_missing_origin_without_credentials() -> None:
    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        hostile = client.post(
            "/api/v1/auth/login",
            headers={"Origin": "https://hostile.example"},
            json={"email": "member@example.invalid", "password": "synthetic-password"},
        )
        missing = client.post(
            "/api/v1/auth/login",
            json={"email": "member@example.invalid", "password": "synthetic-password"},
        )

    assert hostile.status_code == missing.status_code == 403
    assert hostile.json()["error"]["code"] == "ORIGIN_DENIED"
    assert missing.json()["error"]["code"] == "ORIGIN_DENIED"
    assert hostile.headers.get("Access-Control-Allow-Origin") is None


def test_authentication_mutations_reject_form_content_and_missing_csrf() -> None:
    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        form = client.post(
            "/api/v1/auth/login",
            headers={"Origin": settings.frontend_origin},
            data={"email": "member@example.invalid", "password": "synthetic-password"},
        )
        client.cookies.set(
            "__Host-f2s_refresh",
            "synthetic-refresh-credential-value-not-persisted",
        )
        missing_csrf = client.post(
            "/api/v1/auth/refresh",
            headers={"Origin": settings.frontend_origin},
            json={},
        )

    assert form.status_code == 415
    assert form.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert missing_csrf.status_code == 401
    assert missing_csrf.json()["error"]["code"] == "UNAUTHENTICATED"
    assert "Max-Age=0" in missing_csrf.headers["set-cookie"]


def test_failed_refresh_expires_cookie_and_conceals_csrf_details(monkeypatch: object) -> None:
    from app.api import sessions as session_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    monkeypatch.setattr(  # type: ignore[attr-defined]
        session_api,
        "service_for",
        lambda request, session: StubSessionService(None),
    )
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        client.cookies.set(
            "__Host-f2s_refresh",
            "synthetic-refresh-credential-value-not-persisted",
        )
        response = client.post(
            "/api/v1/auth/refresh",
            headers={
                "Origin": settings.frontend_origin,
                "X-CSRF-Token": "synthetic-csrf-credential-value-not-persisted",
            },
            json={},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert "csrf" not in response.text.lower()
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_refresh_is_rate_limited_by_concealed_network(monkeypatch: object) -> None:
    from app.api import sessions as session_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    tokens = _tokens()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        session_api,
        "service_for",
        lambda request, session: StubSessionService(tokens),
    )
    application = create_app(settings)
    application.state.refresh_network_abuse = DevelopmentSubjectAbuseControl(
        limit=30, window=timedelta(minutes=5)
    )
    with TestClient(application, base_url="https://testserver") as client:
        client.cookies.set("__Host-f2s_refresh", tokens.refresh.reveal())
        responses = [
            client.post(
                "/api/v1/auth/refresh",
                headers={
                    "Origin": settings.frontend_origin,
                    "X-CSRF-Token": tokens.csrf.reveal(),
                },
                json={},
            )
            for _ in range(31)
        ]

    assert [response.status_code for response in responses[:30]] == [200] * 30
    assert responses[30].status_code == 429
    assert responses[30].json()["error"]["code"] == "RATE_LIMITED"
    assert int(responses[30].headers["Retry-After"]) > 0
