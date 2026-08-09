"""Role-safe, versioned membership lifecycle API tests."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import Request
from fastapi.testclient import TestClient

from app.api.security import authenticated_account_id
from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app
from app.modules.member_lifecycle import (
    MemberReference,
    MembershipStatus,
    OwnershipInvariantViolation,
)
from app.modules.workspace_access import AuthorizationContext, WorkspaceRole

WORKSPACE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
MEMBERSHIP_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
ADMIN_MEMBERSHIP_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
ACCOUNT_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
NOW = datetime(2026, 8, 9, 10, 0, tzinfo=UTC)


def _member(
    *,
    role: WorkspaceRole = WorkspaceRole.CONTRIBUTOR,
    status: MembershipStatus = MembershipStatus.ACTIVE,
    version: int = 3,
) -> MemberReference:
    return MemberReference(
        id=MEMBERSHIP_ID,
        email="member@example.invalid",
        display_name="Synthetic Member",
        role=role,
        status=status,
        account_status="ACTIVE",
        preferred_language="en",
        timezone="UTC",
        last_login_at=NOW,
        created_at=NOW,
        version=version,
    )


class StubLifecycleService:
    async def list_members(self, context: AuthorizationContext) -> tuple[MemberReference, ...]:
        assert context.role is WorkspaceRole.ADMIN
        return (_member(),)

    async def change_role(
        self,
        context: AuthorizationContext,
        *,
        membership_id: UUID,
        expected_version: int,
        role: WorkspaceRole,
        now: datetime,
    ) -> MemberReference:
        del now
        assert context.role is WorkspaceRole.ADMIN
        assert membership_id == MEMBERSHIP_ID
        assert expected_version == 3
        if role is WorkspaceRole.ADMIN:
            raise OwnershipInvariantViolation
        return _member(role=role, version=4)

    async def suspend(self, context: AuthorizationContext, **values: object) -> MemberReference:
        del context, values
        return _member(status=MembershipStatus.SUSPENDED, version=4)

    async def reactivate(self, context: AuthorizationContext, **values: object) -> MemberReference:
        del context, values
        return _member(status=MembershipStatus.ACTIVE, version=4)

    async def revoke(self, context: AuthorizationContext, **values: object) -> MemberReference:
        del context, values
        return _member(status=MembershipStatus.REVOKED, version=4)


def _client(monkeypatch: object) -> tuple[TestClient, Settings]:
    from app.api import member_lifecycle as lifecycle_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    service = StubLifecycleService()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        lifecycle_api, "service_for", lambda session: service
    )

    async def context(
        request: Request,
        session: object,
        account_id: UUID,
        workspace_id: UUID,
    ) -> AuthorizationContext:
        del request, session
        assert account_id == ACCOUNT_ID
        assert workspace_id == WORKSPACE_ID
        return AuthorizationContext(
            ACCOUNT_ID,
            WORKSPACE_ID,
            ADMIN_MEMBERSHIP_ID,
            WorkspaceRole.ADMIN,
            UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"),
        )

    monkeypatch.setattr(lifecycle_api, "context_or_error", context)  # type: ignore[attr-defined]

    async def audit_denial(*values: object, **named: object) -> None:
        del values, named

    monkeypatch.setattr(  # type: ignore[attr-defined]
        lifecycle_api, "audit_denial", audit_denial
    )
    app = create_app(settings)

    async def authenticated(request: Request) -> UUID:
        request.state.auth_session_id = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
        return ACCOUNT_ID

    app.dependency_overrides[authenticated_account_id] = authenticated
    return TestClient(app, base_url="https://testserver"), settings


def test_admin_member_list_contains_only_safe_membership_profile(monkeypatch: object) -> None:
    client, _ = _client(monkeypatch)
    with client:
        response = client.get(f"/api/v1/workspaces/{WORKSPACE_ID}/members")
    assert response.status_code == 200
    member = response.json()["data"][0]
    assert member["id"] == str(MEMBERSHIP_ID)
    assert member["email"] == "member@example.invalid"
    assert member["role"] == "CONTRIBUTOR"
    assert member["last_login_at"] == "2026-08-09T10:00:00Z"
    assert "user_account_id" not in response.text
    assert "session" not in response.text.lower()
    assert response.headers["Cache-Control"] == "no-store"


def test_patch_requires_browser_boundary_etag_and_one_operation(monkeypatch: object) -> None:
    client, settings = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/members/{MEMBERSHIP_ID}"
    with client:
        missing = client.patch(
            path,
            headers={"Origin": settings.frontend_origin},
            json={"role": "ADVISOR"},
        )
        malformed = client.patch(
            path,
            headers={"Origin": settings.frontend_origin, "If-Match": "3"},
            json={"role": "ADVISOR"},
        )
        hostile = client.patch(
            path,
            headers={"Origin": "https://hostile.example", "If-Match": '"v3"'},
            json={"role": "ADVISOR"},
        )
        ambiguous = client.patch(
            path,
            headers={"Origin": settings.frontend_origin, "If-Match": '"v3"'},
            json={"role": "ADVISOR", "status": "SUSPENDED"},
        )
    assert missing.status_code == 428
    assert malformed.status_code == 412
    assert hostile.status_code == 403
    assert ambiguous.status_code == 422


def test_admin_role_target_requires_dedicated_transfer(monkeypatch: object) -> None:
    client, settings = _client(monkeypatch)
    with client:
        response = client.patch(
            f"/api/v1/workspaces/{WORKSPACE_ID}/members/{MEMBERSHIP_ID}",
            headers={"Origin": settings.frontend_origin, "If-Match": '"v3"'},
            json={"role": "ADMIN"},
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OWNERSHIP_TRANSFER_REQUIRED"


def test_role_reactivate_and_revoke_return_versioned_results(monkeypatch: object) -> None:
    client, settings = _client(monkeypatch)
    headers = {
        "Origin": settings.frontend_origin,
        "If-Match": '"v3"',
        "Content-Type": "application/json",
    }
    with client:
        changed = client.patch(
            f"/api/v1/workspaces/{WORKSPACE_ID}/members/{MEMBERSHIP_ID}",
            headers=headers,
            json={"role": "ADVISOR"},
        )
        reactivated = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/members/{MEMBERSHIP_ID}/reactivate",
            headers=headers,
            json={},
        )
        revoked = client.request(
            "DELETE",
            f"/api/v1/workspaces/{WORKSPACE_ID}/members/{MEMBERSHIP_ID}",
            headers=headers,
            content="{}",
        )
    assert changed.status_code == 200
    assert changed.headers["ETag"] == '"v4"'
    assert changed.json()["data"]["role"] == "ADVISOR"
    assert reactivated.status_code == 200
    assert reactivated.headers["ETag"] == '"v4"'
    assert revoked.status_code == 204
    assert revoked.headers["ETag"] == '"v4"'


def test_activation_restart_is_browser_bound_and_versioned(monkeypatch: object) -> None:
    from app.api import member_activation as activation_api

    client, settings = _client(monkeypatch)

    class StubActivationService:
        async def restart(self, *values: object, **named: object) -> int:
            del values
            assert named["expected_version"] == 3
            return 4

    async def context(
        request: Request,
        session: object,
        account_id: UUID,
        workspace_id: UUID,
    ) -> AuthorizationContext:
        del request, session, account_id, workspace_id
        return AuthorizationContext(
            ACCOUNT_ID,
            WORKSPACE_ID,
            ADMIN_MEMBERSHIP_ID,
            WorkspaceRole.ADMIN,
            UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"),
        )

    monkeypatch.setattr(activation_api, "context_or_error", context)  # type: ignore[attr-defined]
    monkeypatch.setattr(  # type: ignore[attr-defined]
        activation_api, "service_for", lambda request, session: StubActivationService()
    )
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/members/{MEMBERSHIP_ID}/activation/restart"
    with client:
        missing = client.post(
            path,
            headers={"Origin": settings.frontend_origin},
            json={},
        )
        restarted = client.post(
            path,
            headers={"Origin": settings.frontend_origin, "If-Match": '"v3"'},
            json={},
        )
    assert missing.status_code == 428
    assert restarted.status_code == 204
    assert restarted.headers["ETag"] == '"v4"'
