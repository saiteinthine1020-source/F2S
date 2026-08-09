"""Password-change and concealed recovery HTTP-boundary tests."""

from fastapi import Request
from fastapi.testclient import TestClient

from app.api.security import authenticated_account_id
from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app


class StubAccountSecurityService:
    def __init__(self) -> None:
        self.changed = True
        self.completed = True
        self.requests = 0

    async def change_password(self, attempt: object) -> bool:
        del attempt
        return self.changed

    async def request_recovery(self, request: object) -> None:
        del request
        self.requests += 1

    async def confirm_recovery(self, confirmation: object) -> bool:
        del confirmation
        return self.completed


def _client(monkeypatch: object) -> tuple[TestClient, Settings, StubAccountSecurityService]:
    from app.api import account_security as account_security_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    service = StubAccountSecurityService()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        account_security_api,
        "service_for",
        lambda request, session: service,
    )
    app = create_app(settings)

    async def authenticated(request: Request) -> object:
        from uuid import UUID

        request.state.auth_session_id = UUID("22222222-2222-4222-8222-222222222222")
        return UUID("11111111-1111-4111-8111-111111111111")

    app.dependency_overrides[authenticated_account_id] = authenticated
    return TestClient(app, base_url="https://testserver"), settings, service


def test_recovery_request_has_uniform_public_response(monkeypatch: object) -> None:
    client, settings, service = _client(monkeypatch)
    with client:
        first = client.post(
            "/api/v1/auth/recovery/request",
            headers={"Origin": settings.frontend_origin},
            json={"email": "existing@example.invalid"},
        )
        second = client.post(
            "/api/v1/auth/recovery/request",
            headers={"Origin": settings.frontend_origin},
            json={"email": "missing@example.invalid"},
        )
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json() == {"data": {"status": "ACCEPTED"}}
    assert first.headers["Cache-Control"] == "no-store"
    assert service.requests == 2
    assert "existing" not in first.text
    assert "missing" not in second.text


def test_recovery_and_password_mutations_enforce_origin_and_json(monkeypatch: object) -> None:
    client, settings, _ = _client(monkeypatch)
    with client:
        hostile = client.post(
            "/api/v1/auth/recovery/request",
            headers={"Origin": "https://hostile.example"},
            json={"email": "member@example.invalid"},
        )
        form = client.post(
            "/api/v1/auth/recovery/confirm",
            headers={"Origin": settings.frontend_origin},
            data={
                "value": "synthetic-recovery-value-long-enough-for-validation",
                "new_password": "synthetic-recovered-password",
            },
        )
        password = client.post(
            "/api/v1/auth/password/change",
            headers={"Origin": settings.frontend_origin},
            json={
                "current_password": "synthetic-current-password",
                "new_password": "synthetic-replacement-password",
            },
        )
    assert hostile.status_code == 403
    assert hostile.json()["error"]["code"] == "ORIGIN_DENIED"
    assert form.status_code == 415
    assert form.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert password.status_code == 204
    assert password.headers["Cache-Control"] == "no-store"


def test_recovery_confirmation_and_wrong_current_password_are_concealed(
    monkeypatch: object,
) -> None:
    client, settings, service = _client(monkeypatch)
    service.completed = False
    service.changed = False
    with client:
        recovery = client.post(
            "/api/v1/auth/recovery/confirm",
            headers={"Origin": settings.frontend_origin},
            json={
                "value": "synthetic-recovery-value-long-enough-for-validation",
                "new_password": "synthetic-recovered-password",
            },
        )
        password = client.post(
            "/api/v1/auth/password/change",
            headers={"Origin": settings.frontend_origin},
            json={
                "current_password": "synthetic-wrong-password",
                "new_password": "synthetic-replacement-password",
            },
        )
    assert recovery.status_code == password.status_code == 401
    assert recovery.json()["error"]["code"] == "UNAUTHENTICATED"
    assert password.json()["error"]["code"] == "UNAUTHENTICATED"
    assert "value" not in recovery.text.lower()
    assert "password" not in password.text.lower()
