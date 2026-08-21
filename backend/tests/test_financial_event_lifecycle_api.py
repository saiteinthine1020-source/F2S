"""Admin correction, reversal, and archive HTTP contract tests."""

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import Request
from fastapi.testclient import TestClient

from app.api.security import authenticated_account_id
from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app
from app.modules.household_finance import (
    FinancialEventLifecycleRecord,
    FinancialEventLifecycleStateConflict,
    FinancialEventRecord,
    FinancialEventVersionMismatch,
)
from app.modules.workspace_access import AuthorizationContext, WorkspaceRole

WORKSPACE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CATEGORY_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
EVENT_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
MEMBERSHIP_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
ACCOUNT_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
OPERATION_ID = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")


def _record(*, event_id: UUID = EVENT_ID, direction: str = "OUTFLOW") -> FinancialEventRecord:
    return FinancialEventRecord(
        id=event_id,
        event_kind="MANUAL_EXPENSE" if direction == "OUTFLOW" else "MANUAL_INCOME",
        cash_direction=direction,
        activity_classification_code="HOUSEHOLD",
        occurred_on=date(2026, 8, 22),
        finance_category_id=CATEGORY_ID,
        amount=Decimal("20.5000"),
        currency_code="USD",
        payment_method_code="CASH",
        counterparty_text=None,
        reference_text=None,
        notes=None,
        approval_status="APPROVED",
        posting_status="EFFECTIVE",
        version=1,
    )


class StubLifecycleService:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.failure: Exception | None = None

    async def reverse(
        self, context: AuthorizationContext, **values: object
    ) -> tuple[FinancialEventLifecycleRecord, bool]:
        return self._result(context, "reverse")

    async def correct(
        self, context: AuthorizationContext, **values: object
    ) -> tuple[FinancialEventLifecycleRecord, bool]:
        return self._result(context, "correct", replacement=True)

    async def archive(
        self, context: AuthorizationContext, **values: object
    ) -> tuple[FinancialEventRecord, bool]:
        self.calls.append("archive")
        if self.failure is not None:
            raise self.failure
        return replace(_record(), archived_at=datetime.now(UTC), version=2), False

    def _result(
        self, context: AuthorizationContext, action: str, *, replacement: bool = False
    ) -> tuple[FinancialEventLifecycleRecord, bool]:
        assert context.role is WorkspaceRole.ADMIN
        self.calls.append(action)
        if self.failure is not None:
            raise self.failure
        original = replace(_record(), posting_status="REVERSED", version=2)
        reversal = _record(
            event_id=UUID("11111111-1111-4111-8111-111111111111"), direction="INFLOW"
        )
        replacement_record = (
            replace(
                _record(event_id=UUID("22222222-2222-4222-8222-222222222222")),
                amount=Decimal("19.5000"),
            )
            if replacement
            else None
        )
        return FinancialEventLifecycleRecord(original, reversal, replacement_record), False


def _client(monkeypatch: object) -> tuple[TestClient, Settings, StubLifecycleService]:
    from app.api import financial_events as events_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    service = StubLifecycleService()
    monkeypatch.setattr(events_api, "_lifecycle_service", lambda session: service)  # type: ignore[attr-defined]

    async def resolve(
        session: object, *, account_id: UUID, workspace_id: UUID, correlation_id: UUID
    ) -> AuthorizationContext:
        del session
        return AuthorizationContext(
            account_id, workspace_id, MEMBERSHIP_ID, WorkspaceRole.ADMIN, correlation_id
        )

    monkeypatch.setattr(events_api, "_resolve_context", resolve)  # type: ignore[attr-defined]
    app = create_app(settings)

    async def authenticated(request: Request) -> UUID:
        request.state.auth_session_id = UUID("33333333-3333-4333-8333-333333333333")
        return ACCOUNT_ID

    app.dependency_overrides[authenticated_account_id] = authenticated
    return TestClient(app, base_url="https://testserver"), settings, service


def _headers(settings: Settings, key: str) -> dict[str, str]:
    return {
        "Origin": settings.frontend_origin,
        "Idempotency-Key": key,
        "If-Match": '"v1"',
    }


def test_reversal_correction_and_archive_expose_canonical_lifecycle_results(
    monkeypatch: object,
) -> None:
    client, settings, service = _client(monkeypatch)
    base = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events/{EVENT_ID}"
    with client:
        reversal = client.post(
            f"{base}/reversals",
            headers=_headers(settings, "synthetic-reversal-key-0001"),
            json={
                "operation_id": str(OPERATION_ID),
                "occurred_on": "2026-08-23",
                "reason_code": "ENTERED_IN_ERROR",
                "confirmed": True,
            },
        )
        correction = client.post(
            f"{base}/corrections",
            headers=_headers(settings, "synthetic-correction-key-0001"),
            json={
                "operation_id": str(UUID("44444444-4444-4444-8444-444444444444")),
                "reversal_occurred_on": "2026-08-23",
                "reason_code": "INCORRECT_AMOUNT",
                "confirmed": True,
                "replacement": {
                    "event_kind": "MANUAL_EXPENSE",
                    "activity_classification": "HOUSEHOLD",
                    "occurred_on": "2026-08-22",
                    "finance_category_id": str(CATEGORY_ID),
                    "money": {"amount": "19.50", "currency_code": "USD"},
                    "payment_method": "CASH",
                },
            },
        )
        archive = client.post(
            f"{base}/archivals",
            headers=_headers(settings, "synthetic-archive-key-0001"),
            json={
                "operation_id": str(UUID("55555555-5555-4555-8555-555555555555")),
                "reason_code": "DUPLICATE",
                "confirmed": True,
            },
        )

    assert reversal.status_code == 200, reversal.text
    assert reversal.json()["data"]["original"]["posting_status"] == "REVERSED"
    assert reversal.json()["data"]["reversal"]["cash_direction"] == "INFLOW"
    assert correction.status_code == 200, correction.text
    assert correction.json()["data"]["replacement"]["money"]["amount"] == "19.50"
    assert archive.status_code == 200, archive.text
    assert archive.json()["data"]["posting_status"] == "EFFECTIVE"
    assert archive.headers["ETag"] == '"v2"'
    assert service.calls == ["reverse", "correct", "archive"]


def test_lifecycle_commands_require_confirmation_precondition_and_safe_conflicts(
    monkeypatch: object,
) -> None:
    client, settings, service = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events/{EVENT_ID}/reversals"
    payload = {
        "operation_id": str(OPERATION_ID),
        "occurred_on": "2026-08-23",
        "reason_code": "OTHER",
        "confirmed": True,
    }
    with client:
        missing_confirmation = client.post(
            path,
            headers=_headers(settings, "synthetic-reversal-key-0002"),
            json={key: value for key, value in payload.items() if key != "confirmed"},
        )
        missing_precondition = client.post(
            path,
            headers={
                key: value
                for key, value in _headers(settings, "synthetic-reversal-key-0003").items()
                if key != "If-Match"
            },
            json=payload,
        )
        service.failure = FinancialEventVersionMismatch()
        stale = client.post(
            path,
            headers=_headers(settings, "synthetic-reversal-key-0004"),
            json=payload,
        )
        service.failure = FinancialEventLifecycleStateConflict()
        duplicate = client.post(
            path,
            headers=_headers(settings, "synthetic-reversal-key-0005"),
            json=payload,
        )

    assert missing_confirmation.status_code == 422
    assert missing_precondition.status_code == 428
    assert stale.status_code == 412
    assert stale.json()["error"]["code"] == "VERSION_MISMATCH"
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "INVALID_STATE_TRANSITION"
