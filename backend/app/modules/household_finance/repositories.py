"""Framework-free read contracts for workspace-scoped finance persistence."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from app.modules.workspace_access.authorization import AuthorizationContext

if TYPE_CHECKING:
    from app.modules.household_finance.queries import FinancialEventPage, FinancialEventQuery


@dataclass(frozen=True, slots=True)
class FinanceCategoryRecord:
    id: UUID
    display_name: str
    applicability_code: str
    activity_classification_code: str | None
    status: str
    version: int


@dataclass(frozen=True, slots=True)
class FinancialEventRecord:
    id: UUID
    event_kind: str
    cash_direction: str
    activity_classification_code: str
    occurred_on: date
    finance_category_id: UUID
    amount: Decimal
    currency_code: str
    payment_method_code: str
    counterparty_text: str | None
    reference_text: str | None
    notes: str | None
    approval_status: str
    posting_status: str
    version: int
    created_at: datetime | None = None
    archived_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PendingFinancialEventChanges:
    changed_fields: frozenset[str]
    activity_classification_code: str | None = None
    occurred_on: date | None = None
    finance_category_id: UUID | None = None
    amount: Decimal | None = None
    currency_code: str | None = None
    payment_method_code: str | None = None
    counterparty_text: str | None = None
    reference_text: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class FinancialEventStatusRecord:
    action_code: str
    approval_status: str
    actor_membership_id: UUID | None
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class FinancialEventReplacement:
    event_kind: str
    cash_direction: str
    activity_classification_code: str
    occurred_on: date
    finance_category_id: UUID
    amount: Decimal
    currency_code: str
    payment_method_code: str
    counterparty_text: str | None
    reference_text: str | None
    notes: str | None


@dataclass(frozen=True, slots=True)
class FinancialEventLifecycleRecord:
    original: FinancialEventRecord
    reversal: FinancialEventRecord | None = None
    replacement: FinancialEventRecord | None = None


class FinanceRepository(Protocol):
    """Narrow storage contract; policy-specific projections are added by owning issues."""

    async def get_category(
        self, context: AuthorizationContext, *, category_id: UUID
    ) -> FinanceCategoryRecord | None: ...

    async def get_event(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> FinancialEventRecord | None: ...

    async def get_visible_event(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> FinancialEventRecord | None: ...

    async def list_visible_events(
        self,
        context: AuthorizationContext,
        *,
        query: "FinancialEventQuery",
    ) -> "FinancialEventPage": ...

    async def list_event_status_history(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> tuple[FinancialEventStatusRecord, ...] | None: ...

    async def list_categories(
        self, context: AuthorizationContext, *, include_archived: bool
    ) -> tuple[FinanceCategoryRecord, ...]: ...

    async def create_category(
        self,
        context: AuthorizationContext,
        *,
        display_name: str,
        normalized_name: str,
        applicability_code: str,
        activity_classification_code: str | None,
    ) -> FinanceCategoryRecord: ...

    async def rename_category(
        self,
        context: AuthorizationContext,
        *,
        category_id: UUID,
        expected_version: int,
        display_name: str,
        normalized_name: str,
    ) -> FinanceCategoryRecord: ...

    async def archive_category(
        self, context: AuthorizationContext, *, category_id: UUID, expected_version: int
    ) -> FinanceCategoryRecord: ...

    async def create_event(
        self,
        context: AuthorizationContext,
        *,
        operation_id: UUID,
        event_kind: str,
        cash_direction: str,
        activity_classification_code: str,
        occurred_on: date,
        finance_category_id: UUID,
        amount: Decimal,
        currency_code: str,
        payment_method_code: str,
        counterparty_text: str | None,
        reference_text: str | None,
        notes: str | None,
    ) -> FinancialEventRecord: ...

    async def update_pending_event(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        expected_version: int,
        changes: PendingFinancialEventChanges,
    ) -> FinancialEventRecord: ...

    async def decide_pending_event(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        approval_status: str,
        posting_status: str,
        reason_code: str,
        explanation: str | None,
    ) -> FinancialEventRecord: ...

    async def reverse_event(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        expected_version: int,
        operation_id: UUID,
        occurred_on: date,
        reason_code: str,
        correction: bool,
        replacement: FinancialEventReplacement | None,
    ) -> FinancialEventLifecycleRecord: ...

    async def archive_event(
        self,
        context: AuthorizationContext,
        *,
        event_id: UUID,
        expected_version: int,
        reason_code: str,
    ) -> FinancialEventRecord: ...

    async def get_lifecycle_result(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> FinancialEventLifecycleRecord | None: ...

    async def validate_event_category(
        self,
        context: AuthorizationContext,
        *,
        category_id: UUID,
        event_kind: str,
        activity_classification_code: str,
    ) -> None: ...
