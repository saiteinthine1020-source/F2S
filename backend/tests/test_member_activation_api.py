"""Member activation route exposure and fail-closed authentication tests."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app


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
