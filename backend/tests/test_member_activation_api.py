"""Member activation route exposure and fail-closed authentication tests."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app
from app.modules.member_activation import ActivationOutcome


def test_member_management_requires_server_derived_authentication() -> None:
    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    workspace_id = uuid4()
    with TestClient(create_app(settings)) as client:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/members",
            headers={"X-Actor-Account-ID": str(uuid4())},
            json={
                "email": "member@example.invalid",
                "display_name": "Member",
                "role": "CONTRIBUTOR",
                "preferred_language": "en",
                "timezone": "UTC",
            },
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert response.headers["Cache-Control"] == "no-store"
    assert str(workspace_id) not in response.text


def test_public_registration_route_is_not_exposed() -> None:
    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "member@example.invalid", "password": "not-a-real-password"},
        )

    assert response.status_code == 404


class _RejectedActivationService:
    async def activate(self, attempt: object) -> ActivationOutcome:
        del attempt
        return ActivationOutcome(activated=False)


def test_activation_is_rate_limited_by_concealed_subject(monkeypatch: object) -> None:
    from app.api import member_activation as activation_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    monkeypatch.setattr(  # type: ignore[attr-defined]
        activation_api,
        "service_for",
        lambda request, session: _RejectedActivationService(),
    )
    payload = {"value": "synthetic-activation-value-that-is-long-enough"}
    with TestClient(create_app(settings)) as client:
        responses = [
            client.post(
                "/api/v1/auth/activate",
                headers={"Origin": settings.frontend_origin},
                json=payload,
            )
            for _ in range(6)
        ]

    assert [response.status_code for response in responses[:5]] == [401] * 5
    assert responses[5].status_code == 429
    assert responses[5].json()["error"]["code"] == "RATE_LIMITED"
    assert int(responses[5].headers["Retry-After"]) > 0
