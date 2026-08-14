"""Finance-category HTTP contract tests."""

from uuid import UUID

from fastapi import Request
from fastapi.testclient import TestClient

from app.api.security import authenticated_account_id
from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app
from app.modules.household_finance import FinanceCategoryRecord
from app.modules.workspace_access import AuthorizationContext, WorkspaceRole

WORKSPACE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CATEGORY_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
MEMBERSHIP_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
ACCOUNT_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")


class StubFinanceCategoryService:
    async def list_categories(
        self, context: AuthorizationContext, *, include_archived: bool
    ) -> tuple[FinanceCategoryRecord, ...]:
        assert context.workspace_id == WORKSPACE_ID
        assert include_archived
        return (FinanceCategoryRecord(CATEGORY_ID, "Food", "EXPENSE", None, "ACTIVE", 1),)

    async def create(
        self, context: AuthorizationContext, **values: object
    ) -> FinanceCategoryRecord:
        assert context.role is WorkspaceRole.ADMIN
        assert values["name"] == "Food"
        return FinanceCategoryRecord(CATEGORY_ID, "Food", "EXPENSE", None, "ACTIVE", 1)

    async def rename(
        self, context: AuthorizationContext, **values: object
    ) -> FinanceCategoryRecord:
        assert context.role is WorkspaceRole.ADMIN
        assert values["expected_version"] == 1
        return FinanceCategoryRecord(CATEGORY_ID, "Groceries", "EXPENSE", None, "ACTIVE", 2)

    async def archive(
        self, context: AuthorizationContext, **values: object
    ) -> FinanceCategoryRecord:
        assert context.role is WorkspaceRole.ADMIN
        assert values["expected_version"] == 2
        return FinanceCategoryRecord(CATEGORY_ID, "Groceries", "EXPENSE", None, "ARCHIVED", 3)


def _client(monkeypatch: object) -> tuple[TestClient, Settings]:
    from app.api import finance_categories as finance_api

    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    service = StubFinanceCategoryService()
    monkeypatch.setattr(finance_api, "_service", lambda session: service)  # type: ignore[attr-defined]

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

    monkeypatch.setattr(finance_api, "_resolve_context", resolve)  # type: ignore[attr-defined]
    app = create_app(settings)

    async def authenticated(request: Request) -> UUID:
        request.state.auth_session_id = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
        return ACCOUNT_ID

    app.dependency_overrides[authenticated_account_id] = authenticated
    return TestClient(app, base_url="https://testserver"), settings


def test_list_create_rename_and_archive_contracts(monkeypatch: object) -> None:
    client, settings = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/finance-categories"
    mutation_headers = {"Origin": settings.frontend_origin}
    with client:
        listed = client.get(f"{path}?include_archived=true")
        created = client.post(
            path,
            headers=mutation_headers,
            json={"name": "Food", "applicability": "EXPENSE"},
        )
        renamed = client.patch(
            f"{path}/{CATEGORY_ID}",
            headers={**mutation_headers, "If-Match": '"v1"'},
            json={"name": "Groceries"},
        )
        archived = client.post(
            f"{path}/{CATEGORY_ID}/archivals",
            headers={**mutation_headers, "If-Match": '"v2"'},
            json={},
        )
    assert listed.status_code == 200
    assert listed.json()["data"][0]["id"] == str(CATEGORY_ID)
    assert created.status_code == 201
    assert created.headers["ETag"] == '"v1"'
    assert renamed.json()["data"]["name"] == "Groceries"
    assert renamed.headers["ETag"] == '"v2"'
    assert archived.json()["data"]["status"] == "ARCHIVED"
    assert archived.headers["ETag"] == '"v3"'


def test_mutations_require_browser_boundary_and_etag(monkeypatch: object) -> None:
    client, settings = _client(monkeypatch)
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/finance-categories/{CATEGORY_ID}"
    with client:
        missing_origin = client.patch(path, headers={"If-Match": '"v1"'}, json={"name": "X"})
        missing_version = client.patch(
            path, headers={"Origin": settings.frontend_origin}, json={"name": "X"}
        )
        malformed_version = client.patch(
            path,
            headers={"Origin": settings.frontend_origin, "If-Match": "1"},
            json={"name": "X"},
        )
    assert missing_origin.status_code == 403
    assert missing_version.status_code == 428
    assert malformed_version.status_code == 412
