"""Financial-event item, filter, cursor, and role-response HTTP tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import Request
from fastapi.testclient import TestClient

from app.api.security import authenticated_account_id
from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app
from app.modules.household_finance import (
    FinancialEventCursorPosition,
    FinancialEventPage,
    FinancialEventQuery,
    FinancialEventRecord,
    InvalidFinancialEventFilter,
)
from app.modules.workspace_access import AuthorizationContext, WorkspaceRole

WORKSPACE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CATEGORY_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
EVENT_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
MEMBERSHIP_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
ACCOUNT_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
CREATED_AT = datetime(2026, 8, 15, 2, 3, 4, tzinfo=UTC)


def _record() -> FinancialEventRecord:
    return FinancialEventRecord(
        id=EVENT_ID,
        event_kind="MANUAL_EXPENSE",
        cash_direction="OUTFLOW",
        activity_classification_code="HOUSEHOLD",
        occurred_on=date(2026, 8, 14),
        finance_category_id=CATEGORY_ID,
        amount=Decimal("10.5000"),
        currency_code="USD",
        payment_method_code="CASH",
        counterparty_text="Synthetic payee",
        reference_text="SYNTHETIC-REFERENCE",
        notes="Synthetic note",
        approval_status="APPROVED",
        posting_status="EFFECTIVE",
        version=2,
        created_at=CREATED_AT,
    )


class StubFinancialEventQueryService:
    def __init__(self) -> None:
        self.calls = 0
        self.last_query: FinancialEventQuery | None = None
        self.missing = False
        self.denial = False

    async def list_events(
        self, context: AuthorizationContext, *, query: FinancialEventQuery
    ) -> FinancialEventPage:
        self.calls += 1
        self.last_query = query
        if self.denial or (
            context.role is WorkspaceRole.ADVISOR
            and any(status != "APPROVED" for status in query.approval_statuses)
        ):
            raise InvalidFinancialEventFilter
        assert context.workspace_id == WORKSPACE_ID
        return FinancialEventPage(
            (_record(),),
            FinancialEventCursorPosition(date(2026, 8, 14), CREATED_AT, EVENT_ID),
        )

    async def get_event(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> FinancialEventRecord | None:
        self.calls += 1
        assert context.workspace_id == WORKSPACE_ID
        return None if self.missing or event_id != EVENT_ID else _record()


def _client(
    monkeypatch: object,
) -> tuple[TestClient, StubFinancialEventQueryService, dict[str, WorkspaceRole]]:
    from app.api import financial_events as events_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    service = StubFinancialEventQueryService()
    role = {"value": WorkspaceRole.ADMIN}
    monkeypatch.setattr(  # type: ignore[attr-defined]
        events_api, "_query_service", lambda session: service
    )

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

    monkeypatch.setattr(events_api, "_resolve_context", resolve)  # type: ignore[attr-defined]

    async def audit_denial(session: object, context: AuthorizationContext, reason: object) -> None:
        del session, context, reason

    monkeypatch.setattr(  # type: ignore[attr-defined]
        events_api, "_audit_access_denial", audit_denial
    )
    app = create_app(settings)

    async def authenticated(request: Request) -> UUID:
        request.state.auth_session_id = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
        return ACCOUNT_ID

    app.dependency_overrides[authenticated_account_id] = authenticated
    return TestClient(app, base_url="https://testserver"), service, role


def test_filtered_list_returns_exact_values_and_scope_bound_cursor(monkeypatch: object) -> None:
    client, service, _ = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events"
    query = (
        "?status=APPROVED&occurred_from=2026-08-01&occurred_to=2026-09-01"
        f"&category_id={CATEGORY_ID}&event_kind=MANUAL_EXPENSE&direction=OUTFLOW"
        "&activity_classification=HOUSEHOLD&payment_method=CASH&currency=USD"
        "&archived=ACTIVE&page_size=1&sort=-occurred_on,-created_at,id"
    )
    with client:
        first = client.get(path + query)
        cursor = first.json()["meta"]["next_cursor"]
        second = client.get(path + query + f"&after={cursor}")

    assert first.status_code == 200, first.text
    assert first.headers["Cache-Control"] == "no-store"
    assert first.json()["data"][0]["money"] == {
        "amount": "10.50",
        "currency_code": "USD",
    }
    assert first.json()["meta"] == {
        "next_cursor": cursor,
        "page_size": 1,
        "sort": "-occurred_on,-created_at,id",
        "visibility": "ALL_PERMITTED",
    }
    assert "total" not in first.text.lower()
    assert "total_count" not in first.text.lower()
    assert second.status_code == 200
    assert service.last_query is not None
    assert service.last_query.after is not None


def test_cursor_cannot_be_reused_with_changed_filters(monkeypatch: object) -> None:
    client, _, _ = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events"
    with client:
        first = client.get(f"{path}?status=APPROVED&page_size=1")
        cursor = first.json()["meta"]["next_cursor"]
        changed = client.get(f"{path}?status=PENDING&page_size=1&after={cursor}")
        tampered = client.get(f"{path}?status=APPROVED&page_size=1&after={cursor[:-1]}0")

    assert changed.status_code == 400
    assert changed.json()["error"]["code"] == "INVALID_CURSOR"
    assert tampered.status_code == 400
    assert tampered.json()["error"]["code"] == "INVALID_CURSOR"


def test_unknown_sort_and_deferred_farming_filters_fail_safely(monkeypatch: object) -> None:
    client, service, _ = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events"
    with client:
        unknown = client.get(f"{path}?search=secret")
        invalid_sort = client.get(f"{path}?sort=-amount,id")
        farming = client.get(f"{path}?farming_investment_id=11111111-1111-4111-8111-111111111111")
        invalid_dates = client.get(f"{path}?occurred_from=2026-08-15&occurred_to=2026-08-15")

    assert unknown.json()["error"]["code"] == "UNKNOWN_FILTER"
    assert invalid_sort.json()["error"]["code"] == "INVALID_SORT"
    assert farming.json()["error"]["code"] == "INVALID_FILTER"
    assert invalid_dates.json()["error"]["code"] == "INVALID_FILTER"
    assert service.calls == 0
    assert "secret" not in unknown.text


def test_detail_is_etagged_and_missing_id_is_concealed(monkeypatch: object) -> None:
    client, service, _ = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events"
    with client:
        found = client.get(f"{path}/{EVENT_ID}")
        service.missing = True
        missing_id = UUID("11111111-1111-4111-8111-111111111111")
        missing = client.get(f"{path}/{missing_id}")

    assert found.status_code == 200
    assert found.headers["ETag"] == '"v2"'
    assert found.headers["Cache-Control"] == "no-store"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert str(missing_id) not in missing.text


def test_contributor_metadata_declares_own_submission_scope(monkeypatch: object) -> None:
    client, _, role = _client(monkeypatch)
    role["value"] = WorkspaceRole.CONTRIBUTOR
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events"
    with client:
        response = client.get(path)

    assert response.status_code == 200
    assert response.json()["meta"]["visibility"] == "OWN_SUBMISSIONS"
    assert set(response.json()["meta"]) == {
        "next_cursor",
        "page_size",
        "sort",
        "visibility",
    }


def test_advisor_schema_is_approved_only_and_rejects_pending_filter(
    monkeypatch: object,
) -> None:
    client, _, role = _client(monkeypatch)
    role["value"] = WorkspaceRole.ADVISOR
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events"
    with client:
        approved = client.get(f"{path}?status=APPROVED")
        pending = client.get(f"{path}?status=PENDING")

    assert approved.status_code == 200
    assert approved.json()["meta"]["visibility"] == "APPROVED_ONLY"
    assert pending.status_code == 400
    assert pending.json()["error"]["code"] == "INVALID_FILTER"
