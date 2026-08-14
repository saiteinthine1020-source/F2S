"""Manual financial-event HTTP boundary tests."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import Request
from fastapi.testclient import TestClient

from app.api.security import authenticated_account_id
from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app
from app.modules.household_finance import FinancialEventRecord
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    DenialCode,
    WorkspaceRole,
)

WORKSPACE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CATEGORY_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
EVENT_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
OPERATION_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
MEMBERSHIP_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
ACCOUNT_ID = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")


class StubFinancialEventService:
    def __init__(self) -> None:
        self.replayed = False
        self.calls = 0
        self.denial: AuthorizationDenied | None = None

    async def create_manual(
        self, context: AuthorizationContext, **values: object
    ) -> tuple[FinancialEventRecord, bool]:
        self.calls += 1
        if self.denial is not None:
            raise self.denial
        assert context.workspace_id == WORKSPACE_ID
        command = values["command"]
        assert command.amount == "10.50"  # type: ignore[attr-defined]
        assert values["metadata"].operation_id == OPERATION_ID  # type: ignore[attr-defined]
        return (
            FinancialEventRecord(
                id=EVENT_ID,
                event_kind="MANUAL_EXPENSE",
                cash_direction="OUTFLOW",
                activity_classification_code="HOUSEHOLD",
                occurred_on=date(2026, 8, 15),
                finance_category_id=CATEGORY_ID,
                amount=Decimal("10.5000"),
                currency_code="USD",
                payment_method_code="CASH",
                counterparty_text="Synthetic payee",
                reference_text=None,
                notes=None,
                approval_status="APPROVED",
                posting_status="EFFECTIVE",
                version=1,
            ),
            self.replayed,
        )


def _client(monkeypatch: object) -> tuple[TestClient, Settings, StubFinancialEventService]:
    from app.api import financial_events as events_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    service = StubFinancialEventService()
    monkeypatch.setattr(events_api, "_service", lambda session: service)  # type: ignore[attr-defined]

    async def resolve(
        session: object,
        *,
        account_id: UUID,
        workspace_id: UUID,
        correlation_id: UUID,
    ) -> AuthorizationContext:
        del session
        return AuthorizationContext(
            account_id, workspace_id, MEMBERSHIP_ID, WorkspaceRole.ADMIN, correlation_id
        )

    monkeypatch.setattr(events_api, "_resolve_context", resolve)  # type: ignore[attr-defined]

    async def audit_denial(session: object, context: AuthorizationContext) -> None:
        del session, context

    monkeypatch.setattr(  # type: ignore[attr-defined]
        events_api, "_audit_permission_denial", audit_denial
    )
    app = create_app(settings)

    async def authenticated(request: Request) -> UUID:
        request.state.auth_session_id = UUID("11111111-1111-4111-8111-111111111111")
        return ACCOUNT_ID

    app.dependency_overrides[authenticated_account_id] = authenticated
    return TestClient(app, base_url="https://testserver"), settings, service


def _payload() -> dict[str, object]:
    return {
        "operation_id": str(OPERATION_ID),
        "event_kind": "MANUAL_EXPENSE",
        "activity_classification": "HOUSEHOLD",
        "occurred_on": "2026-08-15",
        "finance_category_id": str(CATEGORY_ID),
        "money": {"amount": "10.50", "currency_code": "USD"},
        "payment_method": "CASH",
        "counterparty": "Synthetic payee",
    }


def test_create_returns_exact_money_location_and_replay_metadata(monkeypatch: object) -> None:
    client, settings, service = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events"
    headers = {
        "Origin": settings.frontend_origin,
        "Idempotency-Key": "synthetic-event-key-0001",
    }
    with client:
        created = client.post(path, headers=headers, json=_payload())
        service.replayed = True
        replayed = client.post(path, headers=headers, json=_payload())

    assert created.status_code == 201, created.text
    assert created.headers["Location"].endswith(str(EVENT_ID))
    assert created.headers["Idempotency-Replayed"] == "false"
    assert created.json()["data"]["money"] == {
        "amount": "10.50",
        "currency_code": "USD",
    }
    assert replayed.status_code == 201
    assert replayed.headers["Idempotency-Replayed"] == "true"


def test_create_requires_origin_idempotency_and_decimal_string(monkeypatch: object) -> None:
    client, settings, service = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events"
    valid_headers = {
        "Origin": settings.frontend_origin,
        "Idempotency-Key": "synthetic-event-key-0001",
    }
    numeric_money = _payload()
    numeric_money["money"] = {"amount": 10.5, "currency_code": "USD"}
    with client:
        missing_origin = client.post(
            path,
            headers={"Idempotency-Key": "synthetic-event-key-0001"},
            json=_payload(),
        )
        missing_key = client.post(
            path,
            headers={"Origin": settings.frontend_origin},
            json=_payload(),
        )
        numeric = client.post(path, headers=valid_headers, json=numeric_money)

    assert missing_origin.status_code == 403
    assert missing_key.status_code == 422
    assert numeric.status_code == 422
    assert numeric.json()["error"]["code"] == "VALIDATION_FAILED"
    assert "10.5" not in numeric.text
    assert service.calls == 0


def test_advisor_denial_uses_safe_permission_error(monkeypatch: object) -> None:
    client, settings, service = _client(monkeypatch)
    service.denial = AuthorizationDenied(DenialCode.PERMISSION_DENIED)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events"
    with client:
        response = client.post(
            path,
            headers={
                "Origin": settings.frontend_origin,
                "Idempotency-Key": "synthetic-event-key-0001",
            },
            json=_payload(),
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"
    assert "Synthetic payee" not in response.text
