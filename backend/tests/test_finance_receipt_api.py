"""Protected receipt upload and download HTTP boundary tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Request
from fastapi.testclient import TestClient

from app.api.security import authenticated_account_id
from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app
from app.modules.household_finance import ReceiptRecord
from app.modules.workspace_access import AuthorizationContext, WorkspaceRole

WORKSPACE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
EVENT_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
RECEIPT_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
MEMBERSHIP_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
ACCOUNT_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")


class StubReceiptService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.record = ReceiptRecord(
            RECEIPT_ID,
            EVENT_ID,
            "AVAILABLE",
            "application/pdf",
            "safe-receipt.pdf",
            16,
            "a" * 64,
            now,
            now + timedelta(minutes=15),
            3,
        )

    async def list(
        self, context: AuthorizationContext, **values: object
    ) -> tuple[ReceiptRecord, ...]:
        del context, values
        return (self.record,)

    async def status(self, context: AuthorizationContext, **values: object) -> ReceiptRecord:
        del context, values
        return self.record

    async def upload(self, context: AuthorizationContext, **values: object) -> ReceiptRecord:
        del context, values
        return self.record

    async def authorize_upload(self, context: AuthorizationContext, **values: object) -> None:
        del context, values

    async def download(
        self, context: AuthorizationContext, **values: object
    ) -> tuple[ReceiptRecord, bytes]:
        del context, values
        return self.record, b"synthetic receipt"


def test_receipt_upload_status_list_and_download_are_no_store_and_attachment_only(
    monkeypatch: object,
) -> None:
    from app.api import finance_receipts as receipts_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    service = StubReceiptService()
    monkeypatch.setattr(receipts_api, "_service", lambda request, session: service)  # type: ignore[attr-defined]

    async def context(
        session: object, request: Request, account_id: UUID, workspace_id: UUID
    ) -> AuthorizationContext:
        del session
        return AuthorizationContext(
            account_id,
            workspace_id,
            MEMBERSHIP_ID,
            WorkspaceRole.ADMIN,
            request.state.correlation_id,
        )

    monkeypatch.setattr(receipts_api, "_context", context)  # type: ignore[attr-defined]
    app = create_app(settings)

    async def authenticated(request: Request) -> UUID:
        request.state.auth_session_id = UUID("11111111-1111-4111-8111-111111111111")
        return ACCOUNT_ID

    app.dependency_overrides[authenticated_account_id] = authenticated
    client = TestClient(app, base_url="https://testserver")
    event_path = f"/api/v1/workspaces/{WORKSPACE_ID}/financial-events/{EVENT_ID}/receipts"
    file_path = f"/api/v1/workspaces/{WORKSPACE_ID}/protected-files/{RECEIPT_ID}"
    with client:
        listed = client.get(event_path)
        status_response = client.get(file_path)
        uploaded = client.put(
            f"{file_path}/content",
            content=b"synthetic receipt",
            headers={"Origin": settings.frontend_origin, "Content-Type": "application/pdf"},
        )
        downloaded = client.get(f"{file_path}/download")

    assert listed.status_code == 200 and len(listed.json()["data"]) == 1
    assert status_response.status_code == 200
    assert uploaded.status_code == 200, uploaded.text
    assert downloaded.status_code == 200
    assert downloaded.content == b"synthetic receipt"
    assert downloaded.headers["Cache-Control"] == "no-store"
    assert downloaded.headers["X-Content-Type-Options"] == "nosniff"
    assert downloaded.headers["Content-Disposition"] == 'attachment; filename="safe-receipt.pdf"'
