"""Admin financial-event approval and rejection HTTP contract tests."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import Request
from fastapi.testclient import TestClient

from app.api.security import authenticated_account_id
from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app
from app.modules.application_support import IdempotencyKeyReused
from app.modules.household_finance import (
    FinancialEventDecision,
    FinancialEventRecord,
    FinancialEventStateConflict,
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
OPERATION_ID = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")


def _pending_record() -> FinancialEventRecord:
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
        counterparty_text="Synthetic payee",
        reference_text=None,
        notes=None,
        approval_status="PENDING",
        posting_status="NOT_EFFECTIVE",
        version=1,
    )


class StubDecisionService:
    def __init__(self, role: dict[str, WorkspaceRole]) -> None:
        self.role = role
        self.calls = 0
        self.failure: Exception | None = None
        self.replayed = False

    async def decide(
        self, context: AuthorizationContext, **values: object
    ) -> tuple[FinancialEventRecord, bool]:
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        if self.role["value"] is not WorkspaceRole.ADMIN:
            raise AuthorizationDenied(DenialCode.PERMISSION_DENIED)
        command = values["command"]
        decision = command.decision  # type: ignore[attr-defined]
        record = replace(
            _pending_record(),
            approval_status=(
                "APPROVED" if decision is FinancialEventDecision.APPROVE else "REJECTED"
            ),
            posting_status=(
                "EFFECTIVE" if decision is FinancialEventDecision.APPROVE else "NOT_EFFECTIVE"
            ),
            version=2,
        )
        return record, self.replayed


def _client(
    monkeypatch: object,
) -> tuple[TestClient, Settings, StubDecisionService, dict[str, WorkspaceRole]]:
    from app.api import financial_events as events_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    role = {"value": WorkspaceRole.ADMIN}
    service = StubDecisionService(role)
    monkeypatch.setattr(events_api, "_decision_service", lambda session: service)  # type: ignore[attr-defined]

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
    app = create_app(settings)

    async def authenticated(request: Request) -> UUID:
        request.state.auth_session_id = UUID("11111111-1111-4111-8111-111111111111")
        return ACCOUNT_ID

    app.dependency_overrides[authenticated_account_id] = authenticated
    return TestClient(app, base_url="https://testserver"), settings, service, role


def _headers(settings: Settings) -> dict[str, str]:
    return {
        "Origin": settings.frontend_origin,
        "Idempotency-Key": "synthetic-admin-decision-key-0001",
    }


def test_admin_approval_and_rejection_return_terminal_exact_records(
    monkeypatch: object,
) -> None:
    client, settings, service, _ = _client(monkeypatch)
    base = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events/{EVENT_ID}"
    with client:
        approved = client.post(
            f"{base}/approvals",
            headers=_headers(settings),
            json={
                "operation_id": str(OPERATION_ID),
                "reason_code": "REVIEWED_AND_CONFIRMED",
            },
        )
        service.replayed = True
        rejected = client.post(
            f"{base}/rejections",
            headers={
                **_headers(settings),
                "Idempotency-Key": "synthetic-admin-decision-key-0002",
            },
            json={
                "operation_id": str(UUID("22222222-2222-4222-8222-222222222222")),
                "reason_code": "INSUFFICIENT_EVIDENCE",
                "explanation": "The supporting receipt is not readable.",
            },
        )

    assert approved.status_code == 200, approved.text
    assert approved.headers["ETag"] == '"v2"'
    assert approved.headers["Idempotency-Replayed"] == "false"
    assert approved.headers["Cache-Control"] == "no-store"
    assert approved.json()["data"]["approval_status"] == "APPROVED"
    assert approved.json()["data"]["posting_status"] == "EFFECTIVE"
    assert rejected.status_code == 200, rejected.text
    assert rejected.headers["Idempotency-Replayed"] == "true"
    assert rejected.json()["data"]["approval_status"] == "REJECTED"
    assert rejected.json()["data"]["posting_status"] == "NOT_EFFECTIVE"
    assert service.calls == 2


def test_non_admin_roles_and_stale_or_reused_decisions_are_safe(monkeypatch: object) -> None:
    client, settings, service, role = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events/{EVENT_ID}/approvals"
    payload = {
        "operation_id": str(OPERATION_ID),
        "reason_code": "REVIEWED_AND_CONFIRMED",
    }
    with client:
        role["value"] = WorkspaceRole.CONTRIBUTOR
        contributor = client.post(path, headers=_headers(settings), json=payload)
        role["value"] = WorkspaceRole.ADVISOR
        advisor = client.post(path, headers=_headers(settings), json=payload)
        role["value"] = WorkspaceRole.ADMIN
        service.failure = FinancialEventStateConflict()
        stale = client.post(path, headers=_headers(settings), json=payload)
        service.failure = IdempotencyKeyReused()
        reused = client.post(path, headers=_headers(settings), json=payload)

    assert contributor.status_code == 403
    assert advisor.status_code == 403
    assert contributor.json()["error"]["code"] == "PERMISSION_DENIED"
    assert advisor.json()["error"]["code"] == "PERMISSION_DENIED"
    assert str(EVENT_ID) not in contributor.text
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "INVALID_STATE_TRANSITION"
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_decision_requests_are_strict_and_do_not_reflect_confidential_input(
    monkeypatch: object,
) -> None:
    client, settings, service, _ = _client(monkeypatch)
    base = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events/{EVENT_ID}"
    confidential = "private receipt details must not be reflected"
    with client:
        wrong_approval_reason = client.post(
            f"{base}/approvals",
            headers=_headers(settings),
            json={"operation_id": str(OPERATION_ID), "reason_code": "DUPLICATE"},
        )
        missing_explanation = client.post(
            f"{base}/rejections",
            headers=_headers(settings),
            json={"operation_id": str(OPERATION_ID), "reason_code": "OTHER"},
        )
        unknown = client.post(
            f"{base}/rejections",
            headers=_headers(settings),
            json={
                "operation_id": str(OPERATION_ID),
                "reason_code": "OTHER",
                "explanation": confidential,
                "unexpected": confidential,
            },
        )
        no_key = client.post(
            f"{base}/approvals",
            headers={"Origin": settings.frontend_origin},
            json={
                "operation_id": str(OPERATION_ID),
                "reason_code": "REVIEWED_AND_CONFIRMED",
            },
        )

    assert wrong_approval_reason.status_code == 422
    assert missing_explanation.status_code == 422
    assert unknown.status_code == 422
    assert confidential not in unknown.text
    assert no_key.status_code == 422
    assert service.calls == 0
