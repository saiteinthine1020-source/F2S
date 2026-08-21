"""Role-aware financial-event read contracts and query orchestration."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from app.modules.household_finance.repositories import (
    FinanceRepository,
    FinancialEventRecord,
    FinancialEventStatusRecord,
)
from app.modules.workspace_access import AuthorizationContext, Capability, WorkspaceRole


class FinancialEventArchiveScope(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    ALL = "ALL"


class InvalidFinancialEventFilter(Exception):
    """A safe filter combination is unsupported for the selected role or phase."""


@dataclass(frozen=True, slots=True)
class FinancialEventCursorPosition:
    occurred_on: date
    created_at: datetime
    event_id: UUID

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("CURSOR_TIMEZONE_REQUIRED")


@dataclass(frozen=True, slots=True)
class FinancialEventQuery:
    approval_statuses: tuple[str, ...] = ()
    occurred_from: date | None = None
    occurred_to: date | None = None
    category_ids: tuple[UUID, ...] = ()
    event_kinds: tuple[str, ...] = ()
    cash_directions: tuple[str, ...] = ()
    activity_classifications: tuple[str, ...] = ()
    payment_methods: tuple[str, ...] = ()
    currencies: tuple[str, ...] = ()
    archive_scope: FinancialEventArchiveScope = FinancialEventArchiveScope.ACTIVE
    page_size: int = 25
    after: FinancialEventCursorPosition | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.page_size <= 100:
            raise InvalidFinancialEventFilter
        if (
            self.occurred_from is not None
            and self.occurred_to is not None
            and self.occurred_from >= self.occurred_to
        ):
            raise InvalidFinancialEventFilter


@dataclass(frozen=True, slots=True)
class FinancialEventPage:
    records: tuple[FinancialEventRecord, ...]
    next_position: FinancialEventCursorPosition | None


class FinancialEventQueryService:
    """Expose only the records selected by repository-owned role predicates."""

    def __init__(self, repository: FinanceRepository) -> None:
        self._repository = repository

    async def get_event(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> FinancialEventRecord | None:
        self._require_read_access(context)
        return await self._repository.get_visible_event(context, event_id=event_id)

    async def list_events(
        self, context: AuthorizationContext, *, query: FinancialEventQuery
    ) -> FinancialEventPage:
        self._require_read_access(context)
        self._validate_role_filters(context, query)
        return await self._repository.list_visible_events(context, query=query)

    async def get_status_history(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> tuple[FinancialEventStatusRecord, ...] | None:
        self._require_read_access(context)
        return await self._repository.list_event_status_history(context, event_id=event_id)

    @staticmethod
    def _require_read_access(context: AuthorizationContext) -> None:
        if not context.permits(Capability.ACCESS_WORKSPACE):
            raise InvalidFinancialEventFilter

    @staticmethod
    def _validate_role_filters(context: AuthorizationContext, query: FinancialEventQuery) -> None:
        if context.role is WorkspaceRole.ADVISOR and any(
            status != "APPROVED" for status in query.approval_statuses
        ):
            raise InvalidFinancialEventFilter
