"""Contributor Pending update and status-history HTTP tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import Request
from fastapi.testclient import TestClient

from app.api.security import authenticated_account_id
from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app
from app.modules.household_finance import (
    FinancialEventRecord,
    FinancialEventStateConflict,
    FinancialEventStatusRecord,
    FinancialEventVersionMismatch,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    DenialCode,
    WorkspaceRole,
)

WORKSPACE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CATEGORY_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
EVENT_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
MEMBERSHIP_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
ACCOUNT_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")


def _record() -> FinancialEventRecord:
    return FinancialEventRecord(
        id=EVENT_ID,
        event_kind="MANUAL_EXPENSE",
        cash_direction="OUTFLOW",
        activity_classification_code="HOUSEHOLD",
        occurred_on=date(2026, 8, 21),
        finance_category_id=CATEGORY_ID,
        amount=Decimal("20.5000"),
        currency_code="USD",
        payment_method_code="BANK_TRANSFER",
        counterparty_text="Updated payee",
        reference_text=None,
        notes="Updated note",
        approval_status="PENDING",
        posting_status="NOT_EFFECTIVE",
        version=3,
    )


class StubPendingUpdateService:
    def __init__(self, role: dict[str, WorkspaceRole]) -> None:
        self.role = role
        self.calls = 0
        self.failure: Exception | None = None

    async def update(self, context: AuthorizationContext, **values: object) -> FinancialEventRecord:
        self.calls += 1
        assert values["expected_version"] == 2
        if self.failure is not None:
            raise self.failure
        if self.role["value"] is not WorkspaceRole.CONTRIBUTOR:
            raise AuthorizationDenied(DenialCode.PERMISSION_DENIED)
        command = values["command"]
        assert command.changed_fields == frozenset(  # type: ignore[attr-defined]
            {"money", "payment_method", "counterparty", "reference", "notes"}
        )
        return _record()


class StubStatusHistoryService:
    def __init__(self) -> None:
        self.missing = False

    async def get_status_history(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> tuple[FinancialEventStatusRecord, ...] | None:
        assert context.workspace_id == WORKSPACE_ID
        if self.missing or event_id != EVENT_ID:
            return None
        return (
            FinancialEventStatusRecord(
                "FINANCIAL_EVENT_SUBMITTED",
                "PENDING",
                MEMBERSHIP_ID,
                datetime(2026, 8, 20, 1, 2, 3, tzinfo=UTC),
            ),
            FinancialEventStatusRecord(
                "FINANCIAL_EVENT_PENDING_UPDATED",
                "PENDING",
                MEMBERSHIP_ID,
                datetime(2026, 8, 21, 1, 2, 3, tzinfo=UTC),
            ),
        )


def _client(
    monkeypatch: object,
) -> tuple[
    TestClient,
    Settings,
    StubPendingUpdateService,
    StubStatusHistoryService,
    dict[str, WorkspaceRole],
]:
    from app.api import financial_events as events_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    role = {"value": WorkspaceRole.CONTRIBUTOR}
    update_service = StubPendingUpdateService(role)
    history_service = StubStatusHistoryService()
    monkeypatch.setattr(events_api, "_update_service", lambda session: update_service)  # type: ignore[attr-defined]
    monkeypatch.setattr(events_api, "_query_service", lambda session: history_service)  # type: ignore[attr-defined]

    async def resolve(
        session: object,
        *,
        account_id: UUID,
        workspace_id: UUID,
        correlation_id: UUID,
    ) -> AuthorizationContext:
        del session
        return AuthorizationContext(
            account_id, workspace_id, MEMBERSHIP_ID, role["value"], correlation_id
        )

    async def audit_denial(*args: object, **kwargs: object) -> None:
        del args, kwargs

    monkeypatch.setattr(events_api, "_resolve_context", resolve)  # type: ignore[attr-defined]
    monkeypatch.setattr(events_api, "_audit_permission_denial", audit_denial)  # type: ignore[attr-defined]
    monkeypatch.setattr(events_api, "_audit_access_denial", audit_denial)  # type: ignore[attr-defined]
    app = create_app(settings)

    async def authenticated(request: Request) -> UUID:
        request.state.auth_session_id = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
        return ACCOUNT_ID

    app.dependency_overrides[authenticated_account_id] = authenticated
    return (
        TestClient(app, base_url="https://testserver"),
        settings,
        update_service,
        history_service,
        role,
    )


def _update_payload() -> dict[str, object]:
    return {
        "money": {"amount": "20.50", "currency_code": "USD"},
        "payment_method": "BANK_TRANSFER",
        "counterparty": "Updated payee",
        "reference": None,
        "notes": "Updated note",
    }


def test_contributor_patch_returns_new_etag_and_exact_pending_record(monkeypatch: object) -> None:
    client, settings, service, _, _ = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events/{EVENT_ID}"
    with client:
        response = client.patch(
            path,
            headers={"Origin": settings.frontend_origin, "If-Match": '"v2"'},
            json=_update_payload(),
        )

    assert response.status_code == 200, response.text
    assert response.headers["ETag"] == '"v3"'
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["data"]["money"] == {
        "amount": "20.50",
        "currency_code": "USD",
    }
    assert response.json()["data"]["approval_status"] == "PENDING"
    assert response.json()["data"]["posting_status"] == "NOT_EFFECTIVE"
    assert service.calls == 1


def test_patch_requires_valid_current_version_and_strict_fields(monkeypatch: object) -> None:
    client, settings, service, _, _ = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events/{EVENT_ID}"
    numeric = _update_payload()
    numeric["money"] = {"amount": 20.5, "currency_code": "USD"}
    with client:
        missing = client.patch(
            path, headers={"Origin": settings.frontend_origin}, json={"notes": "x"}
        )
        malformed = client.patch(
            path,
            headers={"Origin": settings.frontend_origin, "If-Match": "2"},
            json={"notes": "x"},
        )
        empty = client.patch(
            path,
            headers={"Origin": settings.frontend_origin, "If-Match": '"v2"'},
            json={},
        )
        numeric_response = client.patch(
            path,
            headers={"Origin": settings.frontend_origin, "If-Match": '"v2"'},
            json=numeric,
        )

    assert missing.status_code == 428
    assert missing.json()["error"]["code"] == "PRECONDITION_REQUIRED"
    assert malformed.status_code == 412
    assert malformed.json()["error"]["code"] == "VERSION_MISMATCH"
    assert empty.status_code == 422
    assert numeric_response.status_code == 422
    assert "20.5" not in numeric_response.text
    assert service.calls == 0


def test_patch_maps_stale_state_and_role_denials_safely(monkeypatch: object) -> None:
    client, settings, service, _, role = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events/{EVENT_ID}"
    headers = {"Origin": settings.frontend_origin, "If-Match": '"v2"'}
    with client:
        service.failure = FinancialEventVersionMismatch()
        stale = client.patch(path, headers=headers, json={"notes": "x"})
        service.failure = FinancialEventStateConflict()
        state = client.patch(path, headers=headers, json={"notes": "x"})
        service.failure = None
        role["value"] = WorkspaceRole.ADVISOR
        advisor = client.patch(path, headers=headers, json={"notes": "x"})

    assert stale.status_code == 412
    assert stale.json()["error"]["code"] == "VERSION_MISMATCH"
    assert state.status_code == 409
    assert state.json()["error"]["code"] == "INVALID_STATE_TRANSITION"
    assert advisor.status_code == 403
    assert advisor.json()["error"]["code"] == "PERMISSION_DENIED"
    assert str(EVENT_ID) not in advisor.text


def test_status_history_is_bounded_and_missing_ids_are_concealed(monkeypatch: object) -> None:
    client, _, _, history, _ = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events/{EVENT_ID}/status-history"
    with client:
        found = client.get(path)
        history.missing = True
        missing = client.get(path)

    assert found.status_code == 200, found.text
    assert found.json()["data"] == [
        {
            "action": "FINANCIAL_EVENT_SUBMITTED",
            "approval_status": "PENDING",
            "actor": "SUBMITTER",
            "occurred_at": "2026-08-20T01:02:03Z",
        },
        {
            "action": "FINANCIAL_EVENT_PENDING_UPDATED",
            "approval_status": "PENDING",
            "actor": "SUBMITTER",
            "occurred_at": "2026-08-21T01:02:03Z",
        },
    ]
    assert str(MEMBERSHIP_ID) not in found.text
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert str(EVENT_ID) not in missing.text
