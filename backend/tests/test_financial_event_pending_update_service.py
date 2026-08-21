"""Contributor Pending financial-event update policy tests."""

import asyncio
from datetime import date
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest

from app.modules.household_finance import (
    ActivityClassification,
    FinanceRepository,
    FinancialEventRecord,
    PaymentMethod,
    PendingFinancialEventChanges,
    PendingFinancialEventUpdateCommand,
    PendingFinancialEventUpdateService,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    WorkspaceRole,
)


class FakePendingEventRepository:
    def __init__(self) -> None:
        self.calls = 0
        self.changes: PendingFinancialEventChanges | None = None
        self.record = FinancialEventRecord(
            id=uuid4(),
            event_kind="MANUAL_EXPENSE",
            cash_direction="OUTFLOW",
            activity_classification_code="HOUSEHOLD",
            occurred_on=date(2026, 8, 20),
            finance_category_id=uuid4(),
            amount=Decimal("10.5000"),
            currency_code="USD",
            payment_method_code="CASH",
            counterparty_text="Previous payee",
            reference_text="REF-1",
            notes="Previous note",
            approval_status="PENDING",
            posting_status="NOT_EFFECTIVE",
            version=2,
        )

    async def update_pending_event(
        self, context: AuthorizationContext, **values: object
    ) -> FinancialEventRecord:
        self.calls += 1
        assert context.role is WorkspaceRole.CONTRIBUTOR
        self.changes = cast(PendingFinancialEventChanges, values["changes"])
        return self.record


def _context(role: WorkspaceRole) -> AuthorizationContext:
    return AuthorizationContext(uuid4(), uuid4(), uuid4(), role, uuid4())


def test_contributor_update_normalizes_exact_allowlisted_changes() -> None:
    async def exercise() -> None:
        repository = FakePendingEventRepository()
        service = PendingFinancialEventUpdateService(cast(FinanceRepository, repository))
        result = await service.update(
            _context(WorkspaceRole.CONTRIBUTOR),
            event_id=repository.record.id,
            expected_version=2,
            command=PendingFinancialEventUpdateCommand(
                changed_fields=frozenset(
                    {
                        "activity_classification",
                        "money",
                        "payment_method",
                        "counterparty",
                        "reference",
                        "notes",
                    }
                ),
                activity_classification=ActivityClassification.BUSINESS,
                amount="20.50",
                currency_code="USD",
                payment_method=PaymentMethod.BANK_TRANSFER,
                counterparty="  Updated payee  ",
                reference=None,
                notes="  Updated note  ",
            ),
        )

        assert result is repository.record
        assert repository.calls == 1
        assert repository.changes is not None
        assert repository.changes.amount == Decimal("20.5000")
        assert repository.changes.currency_code == "USD"
        assert repository.changes.activity_classification_code == "BUSINESS"
        assert repository.changes.payment_method_code == "BANK_TRANSFER"
        assert repository.changes.counterparty_text == "Updated payee"
        assert repository.changes.reference_text is None
        assert repository.changes.notes == "Updated note"

    asyncio.run(exercise())


@pytest.mark.parametrize("role", [WorkspaceRole.ADMIN, WorkspaceRole.ADVISOR])
def test_non_contributors_are_denied_before_repository_access(role: WorkspaceRole) -> None:
    async def exercise() -> None:
        repository = FakePendingEventRepository()
        service = PendingFinancialEventUpdateService(cast(FinanceRepository, repository))
        with pytest.raises(AuthorizationDenied):
            await service.update(
                _context(role),
                event_id=repository.record.id,
                expected_version=2,
                command=PendingFinancialEventUpdateCommand(
                    changed_fields=frozenset({"notes"}),
                    notes="No authority",
                ),
            )
        assert repository.calls == 0

    asyncio.run(exercise())


def test_empty_or_null_required_pending_updates_fail() -> None:
    with pytest.raises(ValueError, match="INVALID_PENDING_EVENT_FIELDS"):
        PendingFinancialEventUpdateCommand(changed_fields=frozenset())
    with pytest.raises(ValueError, match="INVALID_PENDING_EVENT_MONEY"):
        PendingFinancialEventUpdateCommand(
            changed_fields=frozenset({"money"}),
            amount=None,
            currency_code="USD",
        )
