"""Role-aware financial-event query orchestration tests."""

import asyncio
from datetime import date
from typing import cast
from uuid import UUID, uuid4

import pytest

from app.modules.household_finance import (
    FinanceRepository,
    FinancialEventPage,
    FinancialEventQuery,
    FinancialEventQueryService,
    InvalidFinancialEventFilter,
)
from app.modules.workspace_access import AuthorizationContext, WorkspaceRole


class FakeQueryRepository:
    def __init__(self) -> None:
        self.query: FinancialEventQuery | None = None
        self.event_id: UUID | None = None

    async def get_visible_event(self, context: AuthorizationContext, *, event_id: UUID) -> None:
        assert context.workspace_id
        self.event_id = event_id
        return None

    async def list_visible_events(
        self, context: AuthorizationContext, *, query: FinancialEventQuery
    ) -> FinancialEventPage:
        assert context.workspace_id
        self.query = query
        return FinancialEventPage((), None)


def _context(role: WorkspaceRole) -> AuthorizationContext:
    return AuthorizationContext(uuid4(), uuid4(), uuid4(), role, uuid4())


def test_query_service_delegates_role_scoped_reads() -> None:
    async def exercise() -> None:
        repository = FakeQueryRepository()
        service = FinancialEventQueryService(cast(FinanceRepository, repository))
        query = FinancialEventQuery(occurred_from=date(2026, 8, 1))
        await service.list_events(_context(WorkspaceRole.ADMIN), query=query)
        event_id = uuid4()
        await service.get_event(_context(WorkspaceRole.CONTRIBUTOR), event_id=event_id)
        assert repository.query == query
        assert repository.event_id == event_id

    asyncio.run(exercise())


def test_advisor_cannot_request_non_approved_statuses() -> None:
    async def exercise() -> None:
        service = FinancialEventQueryService(cast(FinanceRepository, FakeQueryRepository()))
        with pytest.raises(InvalidFinancialEventFilter):
            await service.list_events(
                _context(WorkspaceRole.ADVISOR),
                query=FinancialEventQuery(approval_statuses=("PENDING",)),
            )

    asyncio.run(exercise())


def test_query_rejects_invalid_page_and_date_range() -> None:
    for query_values in (
        {"page_size": 0},
        {"page_size": 101},
        {"occurred_from": date(2026, 8, 2), "occurred_to": date(2026, 8, 2)},
        {"occurred_from": date(2026, 8, 3), "occurred_to": date(2026, 8, 2)},
    ):
        with pytest.raises(InvalidFinancialEventFilter):
            FinancialEventQuery(**query_values)
