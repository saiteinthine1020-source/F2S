"""Manual financial-event command policy and idempotency unit tests."""

import asyncio
from datetime import date
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest

from app.modules.application_support import (
    ClaimDisposition,
    IdempotencyClaim,
    IdempotencyRepository,
    IdempotencyService,
    IdempotencyState,
    SafeOutcome,
)
from app.modules.household_finance import (
    ActivityClassification,
    FinanceCommandMetadata,
    FinanceRepository,
    FinancialEventCommandService,
    FinancialEventKind,
    FinancialEventRecord,
    ManualFinancialEventCommand,
    PaymentMethod,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    WorkspaceRole,
)
from app.shared_kernel import IdempotencyKey, OperationCode, RequestFingerprint


class FakeEventRepository:
    def __init__(self) -> None:
        self.created = 0
        self.record = FinancialEventRecord(
            id=uuid4(),
            event_kind="MANUAL_INCOME",
            cash_direction="INFLOW",
            activity_classification_code="HOUSEHOLD",
            occurred_on=date(2026, 8, 15),
            finance_category_id=uuid4(),
            amount=Decimal("10.5000"),
            currency_code="USD",
            payment_method_code="CASH",
            counterparty_text="Synthetic source",
            reference_text=None,
            notes=None,
            approval_status="APPROVED",
            posting_status="EFFECTIVE",
            version=1,
        )

    async def get_event(
        self, context: AuthorizationContext, *, event_id: object
    ) -> FinancialEventRecord | None:
        del context
        return self.record if event_id == self.record.id else None

    async def create_event(
        self, context: AuthorizationContext, **values: object
    ) -> FinancialEventRecord:
        self.created += 1
        self.record = FinancialEventRecord(
            id=self.record.id,
            event_kind=cast(str, values["event_kind"]),
            cash_direction=cast(str, values["cash_direction"]),
            activity_classification_code=cast(str, values["activity_classification_code"]),
            occurred_on=cast(date, values["occurred_on"]),
            finance_category_id=cast(UUID, values["finance_category_id"]),
            amount=cast(Decimal, values["amount"]),
            currency_code=cast(str, values["currency_code"]),
            payment_method_code=cast(str, values["payment_method_code"]),
            counterparty_text=cast(str | None, values["counterparty_text"]),
            reference_text=cast(str | None, values["reference_text"]),
            notes=cast(str | None, values["notes"]),
            approval_status="APPROVED" if context.role is WorkspaceRole.ADMIN else "PENDING",
            posting_status="EFFECTIVE" if context.role is WorkspaceRole.ADMIN else "NOT_EFFECTIVE",
            version=1,
        )
        return self.record

    async def validate_event_category(
        self, context: AuthorizationContext, **values: object
    ) -> None:
        del context, values


class FakeIdempotencyRepository:
    def __init__(self) -> None:
        self.event_id = uuid4()
        self.claim_result = IdempotencyClaim(
            uuid4(), ClaimDisposition.STARTED, IdempotencyState.IN_PROGRESS, uuid4(), None
        )
        self.completed: SafeOutcome | None = None

    async def claim(self, context: AuthorizationContext, **values: object) -> IdempotencyClaim:
        del context, values
        return self.claim_result

    async def complete(self, context: AuthorizationContext, **values: object) -> IdempotencyClaim:
        del context
        self.completed = cast(SafeOutcome, values["outcome"])
        return IdempotencyClaim(
            self.claim_result.id,
            ClaimDisposition.REPLAY,
            IdempotencyState.COMPLETED,
            None,
            self.completed,
        )

    async def fail(self, context: AuthorizationContext, **values: object) -> IdempotencyClaim:
        raise AssertionError((context, values))


def _context(role: WorkspaceRole) -> AuthorizationContext:
    return AuthorizationContext(uuid4(), uuid4(), uuid4(), role, uuid4())


def _command(category_id: UUID) -> ManualFinancialEventCommand:
    return ManualFinancialEventCommand(
        event_kind=FinancialEventKind.MANUAL_INCOME,
        activity_classification=ActivityClassification.HOUSEHOLD,
        occurred_on=date(2026, 8, 15),
        finance_category_id=category_id,
        amount="10.50",
        currency_code="USD",
        payment_method=PaymentMethod.CASH,
        counterparty="  Synthetic source  ",
    )


def _metadata() -> FinanceCommandMetadata:
    return FinanceCommandMetadata(
        operation_id=uuid4(),
        operation=OperationCode("CREATE_FINANCIAL_EVENT"),
        idempotency_key=IdempotencyKey("synthetic-event-key-0001"),
        request_fingerprint=RequestFingerprint.from_canonical_bytes(b"synthetic event"),
        required_capability=Capability.CREATE_FINANCIAL_SUBMISSION,
    )


def test_admin_and_contributor_create_exact_role_specific_events() -> None:
    async def exercise() -> None:
        for role, approval, posting in (
            (WorkspaceRole.ADMIN, "APPROVED", "EFFECTIVE"),
            (WorkspaceRole.CONTRIBUTOR, "PENDING", "NOT_EFFECTIVE"),
        ):
            finance = FakeEventRepository()
            idempotency = FakeIdempotencyRepository()
            service = FinancialEventCommandService(
                cast(FinanceRepository, finance),
                IdempotencyService(cast(IdempotencyRepository, idempotency)),
            )
            record, replayed = await service.create_manual(
                _context(role),
                command=_command(finance.record.finance_category_id),
                metadata=_metadata(),
            )
            assert not replayed
            assert record.amount == Decimal("10.5000")
            assert record.approval_status == approval
            assert record.posting_status == posting
            assert record.counterparty_text == "Synthetic source"
            assert idempotency.completed == SafeOutcome(
                "CREATED", 201, "FINANCIAL_EVENT", record.id, 1
            )

    asyncio.run(exercise())


def test_advisor_is_denied_before_money_or_repository_processing() -> None:
    async def exercise() -> None:
        finance = FakeEventRepository()
        idempotency = FakeIdempotencyRepository()
        service = FinancialEventCommandService(
            cast(FinanceRepository, finance),
            IdempotencyService(cast(IdempotencyRepository, idempotency)),
        )
        invalid = _command(finance.record.finance_category_id)
        invalid = ManualFinancialEventCommand(
            event_kind=invalid.event_kind,
            activity_classification=invalid.activity_classification,
            occurred_on=invalid.occurred_on,
            finance_category_id=invalid.finance_category_id,
            amount="not-a-number",
            currency_code=invalid.currency_code,
            payment_method=invalid.payment_method,
        )
        with pytest.raises(AuthorizationDenied):
            await service.create_manual(
                _context(WorkspaceRole.ADVISOR), command=invalid, metadata=_metadata()
            )
        assert finance.created == 0

    asyncio.run(exercise())


def test_matching_terminal_claim_replays_without_second_create() -> None:
    async def exercise() -> None:
        finance = FakeEventRepository()
        idempotency = FakeIdempotencyRepository()
        idempotency.claim_result = IdempotencyClaim(
            idempotency.claim_result.id,
            ClaimDisposition.REPLAY,
            IdempotencyState.COMPLETED,
            None,
            SafeOutcome("CREATED", 201, "FINANCIAL_EVENT", finance.record.id, 1),
        )
        service = FinancialEventCommandService(
            cast(FinanceRepository, finance),
            IdempotencyService(cast(IdempotencyRepository, idempotency)),
        )
        record, replayed = await service.create_manual(
            _context(WorkspaceRole.ADMIN),
            command=_command(finance.record.finance_category_id),
            metadata=_metadata(),
        )
        assert replayed
        assert record.id == finance.record.id
        assert finance.created == 0

    asyncio.run(exercise())
