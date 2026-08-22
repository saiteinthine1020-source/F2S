"""Finance review HTTP contract tests."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import Request
from fastapi.testclient import TestClient

from app.api.security import authenticated_account_id
from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app
from app.modules.household_finance import FinancialEventReviewRecord
from app.modules.workspace_access import AuthorizationContext, WorkspaceRole

WORKSPACE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
EVENT_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
REVIEW_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
MEMBERSHIP_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
ACCOUNT_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
OPERATION_ID = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")


class StubReviewService:
    def __init__(self) -> None:
        self.record = FinancialEventReviewRecord(
            REVIEW_ID,
            EVENT_ID,
            "FLAG",
            "Check the receipt",
            "MISSING_EVIDENCE",
            "OPEN",
            MEMBERSHIP_ID,
            datetime(2026, 8, 22, tzinfo=UTC),
            None,
            None,
            None,
            1,
        )

    async def list_reviews(
        self, context: AuthorizationContext, **values: object
    ) -> tuple[FinancialEventReviewRecord, ...]:
        del context, values
        return (self.record,)

    async def create(
        self, context: AuthorizationContext, **values: object
    ) -> tuple[FinancialEventReviewRecord, bool]:
        del context, values
        return self.record, False

    async def resolve(
        self, context: AuthorizationContext, **values: object
    ) -> FinancialEventReviewRecord:
        del context, values
        self.record = FinancialEventReviewRecord(
            self.record.id,
            self.record.financial_event_id,
            self.record.review_kind,
            self.record.body_text,
            self.record.reason_code,
            "RESOLVED",
            self.record.created_by_membership_id,
            self.record.created_at,
            MEMBERSHIP_ID,
            datetime(2026, 8, 23, tzinfo=UTC),
            "REVIEWED_NO_CHANGE",
            2,
        )
        return self.record


def test_review_create_list_and_resolution_contract(monkeypatch: object) -> None:
    from app.api import financial_event_reviews as reviews_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    service = StubReviewService()
    monkeypatch.setattr(reviews_api, "_service", lambda session: service)  # type: ignore[attr-defined]

    async def context(
        session: object, request: Request, account_id: UUID, workspace_id: UUID
    ) -> AuthorizationContext:
        del session
        return AuthorizationContext(
            account_id,
            workspace_id,
            MEMBERSHIP_ID,
            WorkspaceRole.ADVISOR,
            request.state.correlation_id,
        )

    monkeypatch.setattr(reviews_api, "_context", context)  # type: ignore[attr-defined]
    app = create_app(settings)

    async def authenticated(request: Request) -> UUID:
        request.state.auth_session_id = UUID("11111111-1111-4111-8111-111111111111")
        return ACCOUNT_ID

    app.dependency_overrides[authenticated_account_id] = authenticated
    client = TestClient(app, base_url="https://testserver")
    base = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events/{EVENT_ID}/reviews"
    headers = {
        "Origin": settings.frontend_origin,
        "Idempotency-Key": "synthetic-review-key-0001",
    }
    with client:
        created = client.post(
            base,
            headers=headers,
            json={
                "operation_id": str(OPERATION_ID),
                "kind": "FLAG",
                "body": "Check the receipt",
                "reason_code": "MISSING_EVIDENCE",
            },
        )
        listed = client.get(base)
        resolved = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/financial-event-reviews/{REVIEW_ID}/resolutions",
            headers={"Origin": settings.frontend_origin, "If-Match": '"v1"'},
            json={"resolution_code": "REVIEWED_NO_CHANGE"},
        )

    assert created.status_code == 201, created.text
    assert created.headers["ETag"] == '"v1"'
    assert created.headers["Idempotency-Replayed"] == "false"
    assert listed.status_code == 200 and len(listed.json()["data"]) == 1
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["data"]["status"] == "RESOLVED"
    assert resolved.headers["ETag"] == '"v2"'
