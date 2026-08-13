"""Framework-free read contracts for workspace-scoped finance persistence."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.modules.workspace_access.authorization import AuthorizationContext


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
    occurred_on: date
    amount: Decimal
    currency_code: str
    approval_status: str
    posting_status: str
    version: int


class FinanceRepository(Protocol):
    """Narrow storage contract; policy-specific projections are added by owning issues."""

    async def get_category(
        self, context: AuthorizationContext, *, category_id: UUID
    ) -> FinanceCategoryRecord | None: ...

    async def get_event(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> FinancialEventRecord | None: ...
