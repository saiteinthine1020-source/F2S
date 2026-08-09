"""Browser-bound ownership-transfer API contract tests."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import Request
from fastapi.testclient import TestClient

from app.api.security import authenticated_account_id
from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app
from app.modules.ownership_transfer import (
    CancelOwnershipTransfer,
    ConfirmOwnershipTransfer,
    InitiateOwnershipTransfer,
    OwnershipTransferReference,
    OwnershipTransferStatus,
)
from app.modules.workspace_access import AuthorizationContext, WorkspaceRole

WORKSPACE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TRANSFER_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
OWNER_MEMBERSHIP_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
TARGET_MEMBERSHIP_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
ACCOUNT_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
SESSION_ID = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
NOW = datetime(2026, 8, 9, 10, 0, tzinfo=UTC)


class StubService:
    def __init__(self) -> None:
        self.initiated: InitiateOwnershipTransfer | None = None
        self.confirmed: ConfirmOwnershipTransfer | None = None
        self.cancelled: CancelOwnershipTransfer | None = None

    def _reference(
        self, status: OwnershipTransferStatus, version: int
    ) -> OwnershipTransferReference:
        return OwnershipTransferReference(
            TRANSFER_ID,
            WORKSPACE_ID,
            OWNER_MEMBERSHIP_ID,
            TARGET_MEMBERSHIP_ID,
            WorkspaceRole.CONTRIBUTOR,
            status,
            NOW,
            version,
        )

    async def initiate(self, command: InitiateOwnershipTransfer) -> OwnershipTransferReference:
        self.initiated = command
        return self._reference(OwnershipTransferStatus.INITIATED, 1)

    async def confirm(self, command: ConfirmOwnershipTransfer) -> OwnershipTransferReference:
        self.confirmed = command
        return self._reference(OwnershipTransferStatus.COMPLETED, 3)

    async def cancel(self, command: CancelOwnershipTransfer) -> None:
        self.cancelled = command


def _client(monkeypatch: object) -> tuple[TestClient, Settings, StubService]:
    from app.api import ownership_transfer as transfer_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    service = StubService()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        transfer_api, "service_for", lambda request, session: service
    )

    async def context(
        request: Request,
        session: object,
        account_id: UUID,
        workspace_id: UUID,
    ) -> AuthorizationContext:
        del request, session
        return AuthorizationContext(
            account_id,
            workspace_id,
            OWNER_MEMBERSHIP_ID,
            WorkspaceRole.ADMIN,
            UUID("11111111-1111-4111-8111-111111111111"),
        )

    monkeypatch.setattr(transfer_api, "context_or_error", context)  # type: ignore[attr-defined]
    app = create_app(settings)

    async def authenticated(request: Request) -> UUID:
        request.state.auth_session_id = SESSION_ID
        return ACCOUNT_ID

    app.dependency_overrides[authenticated_account_id] = authenticated
    return TestClient(app, base_url="https://testserver"), settings, service


def test_initiate_requires_exact_browser_boundary_and_returns_versioned_resource(
    monkeypatch: object,
) -> None:
    client, settings, service = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/ownership-transfers"
    body = {
        "target_membership_id": str(TARGET_MEMBERSHIP_ID),
        "former_owner_role": "CONTRIBUTOR",
        "current_password": "synthetic-current-password",
    }
    with client:
        hostile = client.post(path, headers={"Origin": "https://hostile.invalid"}, json=body)
        response = client.post(path, headers={"Origin": settings.frontend_origin}, json=body)
    assert hostile.status_code == 403
    assert response.status_code == 201
    assert response.headers["ETag"] == '"v1"'
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["data"]["status"] == "INITIATED"
    assert "current_password" not in response.text
    assert service.initiated is not None
    assert service.initiated.current_session_id == SESSION_ID


def test_only_authenticated_target_confirmation_contract_is_forwarded(
    monkeypatch: object,
) -> None:
    client, settings, service = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/ownership-transfers/{TRANSFER_ID}/confirm"
    with client:
        response = client.post(
            path,
            headers={"Origin": settings.frontend_origin},
            json={"value": "x" * 32},
        )
    assert response.status_code == 200
    assert response.headers["ETag"] == '"v3"'
    assert response.json()["data"]["status"] == "COMPLETED"
    assert service.confirmed is not None
    assert service.confirmed.transfer_id == TRANSFER_ID


def test_cancel_requires_etag_and_empty_json(monkeypatch: object) -> None:
    client, settings, service = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/ownership-transfers/{TRANSFER_ID}/cancel"
    with client:
        missing = client.post(path, headers={"Origin": settings.frontend_origin}, json={})
        cancelled = client.post(
            path,
            headers={"Origin": settings.frontend_origin, "If-Match": '"v1"'},
            json={},
        )
    assert missing.status_code == 428
    assert cancelled.status_code == 204
    assert service.cancelled is not None and service.cancelled.expected_version == 1
