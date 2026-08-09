"""Workspace list, selected retrieval, and optimistic settings API tests."""

from uuid import UUID

from fastapi import Request
from fastapi.testclient import TestClient

from app.api.security import authenticated_account_id
from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    DenialCode,
    ModuleCode,
    SelectedWorkspace,
    WorkspaceAdministration,
    WorkspaceMembershipReference,
    WorkspaceModuleReference,
    WorkspaceReference,
    WorkspaceRole,
    WorkspaceSettingsSnapshot,
)

WORKSPACE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
MEMBERSHIP_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
ACCOUNT_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def _workspace(version: int = 3) -> WorkspaceReference:
    return WorkspaceReference(
        WORKSPACE_ID,
        "Synthetic Workspace",
        "HOUSEHOLD",
        "USD",
        "UTC",
        "en",
        version,
    )


def _modules() -> tuple[WorkspaceModuleReference, ...]:
    return (
        WorkspaceModuleReference(
            UUID("11111111-1111-4111-8111-111111111111"), "FARMING_INVESTMENTS", False, 1
        ),
        WorkspaceModuleReference(
            UUID("22222222-2222-4222-8222-222222222222"), "HOUSEHOLD_FINANCE", True, 1
        ),
    )


class StubWorkspaceSettingsService:
    def __init__(self) -> None:
        self.role = WorkspaceRole.ADMIN
        self.deny_update = False
        self.reject_update = False

    async def list_for_account(self, account_id: UUID) -> tuple[WorkspaceMembershipReference, ...]:
        assert account_id == ACCOUNT_ID
        return (WorkspaceMembershipReference(MEMBERSHIP_ID, self.role.value, _workspace()),)

    async def get_selected(self, context: AuthorizationContext) -> SelectedWorkspace:
        administration = (
            WorkspaceAdministration(
                WORKSPACE_ID, "Private profile", "Private address", None, None, 3
            )
            if context.role is WorkspaceRole.ADMIN
            else None
        )
        return SelectedWorkspace(_workspace(), _modules(), administration)

    async def update(
        self, context: AuthorizationContext, **values: object
    ) -> WorkspaceSettingsSnapshot:
        if self.deny_update:
            raise AuthorizationDenied(DenialCode.PERMISSION_DENIED)
        if self.reject_update:
            raise ValueError("INVALID_SETTINGS")
        assert context.role is WorkspaceRole.ADMIN
        assert values["expected_version"] == 3
        return WorkspaceSettingsSnapshot(
            _workspace(4),
            WorkspaceAdministration(WORKSPACE_ID, "Updated", None, None, None, 4),
            (
                WorkspaceModuleReference(
                    UUID("11111111-1111-4111-8111-111111111111"),
                    ModuleCode.FARMING_INVESTMENTS.value,
                    True,
                    2,
                ),
                _modules()[1],
            ),
        )


def _client(monkeypatch: object) -> tuple[TestClient, Settings, StubWorkspaceSettingsService]:
    from app.api import workspace_settings as workspace_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    service = StubWorkspaceSettingsService()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        workspace_api, "service_for", lambda session: service
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        workspace_api, "directory_service_for", lambda session: service
    )

    async def resolve(
        session: object,
        *,
        actor_account_id: UUID,
        workspace_id: UUID,
        correlation_id: UUID,
    ) -> AuthorizationContext:
        del session
        return AuthorizationContext(
            actor_account_id,
            workspace_id,
            MEMBERSHIP_ID,
            service.role,
            correlation_id,
        )

    monkeypatch.setattr(workspace_api, "_resolve_context", resolve)  # type: ignore[attr-defined]
    app = create_app(settings)

    async def authenticated(request: Request) -> UUID:
        request.state.auth_session_id = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
        return ACCOUNT_ID

    app.dependency_overrides[authenticated_account_id] = authenticated
    return TestClient(app, base_url="https://testserver"), settings, service


def test_list_and_selected_workspace_return_only_role_safe_fields(monkeypatch: object) -> None:
    client, _, service = _client(monkeypatch)
    with client:
        listed = client.get("/api/v1/me/workspaces")
        service.role = WorkspaceRole.CONTRIBUTOR
        selected = client.get(f"/api/v1/workspaces/{WORKSPACE_ID}")
    assert listed.status_code == 200
    assert listed.json()["data"][0]["workspace"]["id"] == str(WORKSPACE_ID)
    assert listed.json()["data"][0]["role"] == "ADMIN"
    assert selected.status_code == 200
    assert selected.headers["ETag"] == '"v3"'
    assert "administration" not in selected.json()["data"]
    assert "Private profile" not in selected.text
    assert {item["code"] for item in selected.json()["data"]["modules"]} == {
        "HOUSEHOLD_FINANCE",
        "FARMING_INVESTMENTS",
    }


def test_patch_requires_origin_json_and_current_etag(monkeypatch: object) -> None:
    client, settings, _ = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}"
    with client:
        missing = client.patch(
            path,
            headers={"Origin": settings.frontend_origin},
            json={"name": "Updated"},
        )
        hostile = client.patch(
            path,
            headers={"Origin": "https://hostile.example", "If-Match": '"v3"'},
            json={"name": "Updated"},
        )
        malformed = client.patch(
            path,
            headers={"Origin": settings.frontend_origin, "If-Match": "3"},
            json={"name": "Updated"},
        )
        form = client.patch(
            path,
            headers={"Origin": settings.frontend_origin, "If-Match": '"v3"'},
            data={"name": "Updated"},
        )
    assert missing.status_code == 428
    assert missing.json()["error"]["code"] == "PRECONDITION_REQUIRED"
    assert hostile.status_code == 403
    assert malformed.status_code == 412
    assert malformed.json()["error"]["code"] == "VERSION_MISMATCH"
    assert form.status_code == 415


def test_admin_patch_returns_incremented_etag_and_complete_configuration(
    monkeypatch: object,
) -> None:
    client, settings, _ = _client(monkeypatch)
    with client:
        response = client.patch(
            f"/api/v1/workspaces/{WORKSPACE_ID}",
            headers={"Origin": settings.frontend_origin, "If-Match": '"v3"'},
            json={
                "description": "Updated",
                "modules": [{"code": "FARMING_INVESTMENTS", "enabled": True}],
            },
        )
    assert response.status_code == 200
    assert response.headers["ETag"] == '"v4"'
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["data"]["workspace"]["id"] == str(WORKSPACE_ID)
    assert response.json()["data"]["administration"]["description"] == "Updated"
    assert response.json()["data"]["modules"][0]["enabled"] is True


def test_non_admin_patch_is_denied_and_audited(monkeypatch: object) -> None:
    from app.api import workspace_settings as workspace_api

    client, settings, service = _client(monkeypatch)
    service.role = WorkspaceRole.CONTRIBUTOR
    service.deny_update = True
    audit_calls: list[tuple[WorkspaceRole, object]] = []

    async def audit_denial(session: object, context: AuthorizationContext, reason: object) -> None:
        del session
        audit_calls.append((context.role, reason))

    monkeypatch.setattr(  # type: ignore[attr-defined]
        workspace_api, "_audit_settings_denial", audit_denial
    )
    with client:
        response = client.patch(
            f"/api/v1/workspaces/{WORKSPACE_ID}",
            headers={"Origin": settings.frontend_origin, "If-Match": '"v3"'},
            json={"name": "Forbidden"},
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"
    assert len(audit_calls) == 1
    assert audit_calls[0][0] is WorkspaceRole.CONTRIBUTOR


def test_business_validation_failure_is_safe_and_audited(monkeypatch: object) -> None:
    from app.api import workspace_settings as workspace_api

    client, settings, service = _client(monkeypatch)
    service.reject_update = True
    audit_calls: list[object] = []

    async def audit_denial(session: object, context: AuthorizationContext, reason: object) -> None:
        del session, context
        audit_calls.append(reason)

    monkeypatch.setattr(  # type: ignore[attr-defined]
        workspace_api, "_audit_settings_denial", audit_denial
    )
    with client:
        response = client.patch(
            f"/api/v1/workspaces/{WORKSPACE_ID}",
            headers={"Origin": settings.frontend_origin, "If-Match": '"v3"'},
            json={"timezone": "Not/A_Real_Zone"},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert len(audit_calls) == 1
