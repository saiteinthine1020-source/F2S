"""Append-only financial-event lifecycle policy unit tests."""

import asyncio
from dataclasses import replace
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
    FinancialEventArchiveCommand,
    FinancialEventCorrectionCommand,
    FinancialEventKind,
    FinancialEventLifecycleReason,
    FinancialEventLifecycleRecord,
    FinancialEventLifecycleService,
    FinancialEventLifecycleStateConflict,
    FinancialEventRecord,
    FinancialEventReplacement,
    FinancialEventReversalCommand,
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


def _record(*, direction: str = "OUTFLOW") -> FinancialEventRecord:
    return FinancialEventRecord(
        id=uuid4(),
        event_kind="MANUAL_EXPENSE" if direction == "OUTFLOW" else "MANUAL_INCOME",
        cash_direction=direction,
        activity_classification_code="HOUSEHOLD",
        occurred_on=date(2026, 8, 22),
        finance_category_id=uuid4(),
        amount=Decimal("25.0000"),
        currency_code="USD",
        payment_method_code="CASH",
        counterparty_text=None,
        reference_text=None,
        notes=None,
        approval_status="APPROVED",
        posting_status="EFFECTIVE",
        version=1,
    )


class FakeLifecycleRepository:
    def __init__(self) -> None:
        self.original = _record()
        self.reversal: FinancialEventRecord | None = None
        self.replacement: FinancialEventRecord | None = None
        self.archived: FinancialEventRecord | None = None
        self.reverse_calls = 0
        self.archive_calls = 0
        self.failure: Exception | None = None

    async def validate_event_category(
        self, context: AuthorizationContext, **values: object
    ) -> None:
        del context, values

    async def reverse_event(
        self, context: AuthorizationContext, **values: object
    ) -> FinancialEventLifecycleRecord:
        assert context.role is WorkspaceRole.ADMIN
        self.reverse_calls += 1
        if self.failure is not None:
            raise self.failure
        self.original = replace(self.original, posting_status="REVERSED", version=2)
        self.reversal = replace(
            _record(direction="INFLOW"),
            amount=self.original.amount,
            currency_code=self.original.currency_code,
            occurred_on=cast(date, values["occurred_on"]),
        )
        replacement = cast(FinancialEventReplacement | None, values["replacement"])
        if replacement is not None:
            self.replacement = replace(
                _record(direction=replacement.cash_direction),
                event_kind=replacement.event_kind,
                amount=replacement.amount,
                currency_code=replacement.currency_code,
            )
        return FinancialEventLifecycleRecord(self.original, self.reversal, self.replacement)

    async def archive_event(
        self, context: AuthorizationContext, **values: object
    ) -> FinancialEventRecord:
        assert context.role is WorkspaceRole.ADMIN
        self.archive_calls += 1
        if self.failure is not None:
            raise self.failure
        self.archived = replace(self.original, archived_at=self.original.created_at, version=2)
        return self.archived

    async def get_event(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> FinancialEventRecord | None:
        del context
        if event_id != self.original.id:
            return None
        return self.archived or self.original

    async def get_lifecycle_result(
        self, context: AuthorizationContext, *, event_id: UUID
    ) -> FinancialEventLifecycleRecord | None:
        del context
        if event_id != self.original.id:
            return None
        return FinancialEventLifecycleRecord(self.original, self.reversal, self.replacement)


class FakeIdempotencyRepository:
    def __init__(self) -> None:
        self.claim_result = IdempotencyClaim(
            uuid4(), ClaimDisposition.STARTED, IdempotencyState.IN_PROGRESS, uuid4(), None
        )
        self.completed: SafeOutcome | None = None
        self.failed: SafeOutcome | None = None

    async def claim(self, context: AuthorizationContext, **values: object) -> IdempotencyClaim:
        del context, values
        return self.claim_result

    async def complete(self, context: AuthorizationContext, **values: object) -> IdempotencyClaim:
        del context
        self.completed = cast(SafeOutcome, values["outcome"])
        return replace(
            self.claim_result,
            disposition=ClaimDisposition.REPLAY,
            state=IdempotencyState.COMPLETED,
            outcome=self.completed,
        )

    async def fail(self, context: AuthorizationContext, **values: object) -> IdempotencyClaim:
        del context
        self.failed = cast(SafeOutcome, values["outcome"])
        return replace(
            self.claim_result,
            disposition=ClaimDisposition.REPLAY,
            state=IdempotencyState.FAILED,
            outcome=self.failed,
        )


def _context(role: WorkspaceRole = WorkspaceRole.ADMIN) -> AuthorizationContext:
    return AuthorizationContext(uuid4(), uuid4(), uuid4(), role, uuid4())


def _metadata(operation: str) -> FinanceCommandMetadata:
    return FinanceCommandMetadata(
        uuid4(),
        OperationCode(operation),
        IdempotencyKey(f"lifecycle-{operation.lower()}-0001"),
        RequestFingerprint.from_canonical_bytes(operation.encode("ascii")),
        Capability.APPROVE_OR_REJECT_SUBMISSIONS,
    )


def _service() -> tuple[
    FinancialEventLifecycleService, FakeLifecycleRepository, FakeIdempotencyRepository
]:
    finance = FakeLifecycleRepository()
    idempotency = FakeIdempotencyRepository()
    return (
        FinancialEventLifecycleService(
            cast(FinanceRepository, finance),
            IdempotencyService(cast(IdempotencyRepository, idempotency)),
        ),
        finance,
        idempotency,
    )


def test_reversal_conserves_exact_amount_once_and_records_terminal_outcome() -> None:
    async def exercise() -> None:
        service, finance, idempotency = _service()
        result, replayed = await service.reverse(
            _context(),
            event_id=finance.original.id,
            expected_version=1,
            command=FinancialEventReversalCommand(
                date(2026, 8, 23), FinancialEventLifecycleReason.ENTERED_IN_ERROR, True
            ),
            metadata=_metadata("REVERSE_FINANCIAL_EVENT"),
        )
        assert not replayed
        assert result.original.posting_status == "REVERSED"
        assert result.reversal is not None
        assert result.reversal.amount == result.original.amount
        assert result.reversal.currency_code == result.original.currency_code
        assert result.reversal.cash_direction != result.original.cash_direction
        assert finance.reverse_calls == 1
        assert idempotency.completed == SafeOutcome(
            "REVERSED", 200, "FINANCIAL_EVENT", result.original.id, 2
        )

    asyncio.run(exercise())


def test_correction_builds_exact_approved_replacement_and_archive_preserves_posting() -> None:
    async def exercise() -> None:
        service, finance, _ = _service()
        result, _ = await service.correct(
            _context(),
            event_id=finance.original.id,
            expected_version=1,
            command=FinancialEventCorrectionCommand(
                date(2026, 8, 23),
                FinancialEventLifecycleReason.INCORRECT_AMOUNT,
                True,
                ManualFinancialEventCommand(
                    FinancialEventKind.MANUAL_EXPENSE,
                    ActivityClassification.HOUSEHOLD,
                    date(2026, 8, 22),
                    finance.original.finance_category_id,
                    "20.50",
                    "USD",
                    PaymentMethod.CASH,
                ),
            ),
            metadata=_metadata("CORRECT_FINANCIAL_EVENT"),
        )
        assert result.replacement is not None
        assert result.replacement.amount == Decimal("20.5000")
        assert result.replacement.posting_status == "EFFECTIVE"

        archive_service, archive_finance, _ = _service()
        archived, _ = await archive_service.archive(
            _context(),
            event_id=archive_finance.original.id,
            expected_version=1,
            command=FinancialEventArchiveCommand(FinancialEventLifecycleReason.DUPLICATE, True),
            metadata=_metadata("ARCHIVE_FINANCIAL_EVENT"),
        )
        assert archived.posting_status == "EFFECTIVE"
        assert archived.version == 2

    asyncio.run(exercise())


@pytest.mark.parametrize("role", [WorkspaceRole.CONTRIBUTOR, WorkspaceRole.ADVISOR])
def test_non_admin_and_missing_confirmation_are_rejected_before_storage(
    role: WorkspaceRole,
) -> None:
    async def exercise() -> None:
        service, finance, _ = _service()
        with pytest.raises(AuthorizationDenied):
            await service.reverse(
                _context(role),
                event_id=finance.original.id,
                expected_version=1,
                command=FinancialEventReversalCommand(
                    date.today(), FinancialEventLifecycleReason.OTHER, True
                ),
                metadata=_metadata("REVERSE_FINANCIAL_EVENT"),
            )
        with pytest.raises(ValueError, match="CONFIRMATION_REQUIRED"):
            await service.reverse(
                _context(),
                event_id=finance.original.id,
                expected_version=1,
                command=FinancialEventReversalCommand(
                    date.today(), FinancialEventLifecycleReason.OTHER, False
                ),
                metadata=_metadata("REVERSE_FINANCIAL_EVENT"),
            )
        assert finance.reverse_calls == 0

    asyncio.run(exercise())


def test_state_conflict_is_stored_and_matching_success_replays_without_second_write() -> None:
    async def exercise() -> None:
        service, finance, idempotency = _service()
        finance.failure = FinancialEventLifecycleStateConflict()
        command = FinancialEventReversalCommand(
            date.today(), FinancialEventLifecycleReason.DUPLICATE, True
        )
        metadata = _metadata("REVERSE_FINANCIAL_EVENT")
        with pytest.raises(FinancialEventLifecycleStateConflict):
            await service.reverse(
                _context(),
                event_id=finance.original.id,
                expected_version=1,
                command=command,
                metadata=metadata,
            )
        assert idempotency.failed == SafeOutcome("INVALID_STATE_TRANSITION", 409)

        finance.failure = None
        finance.original = replace(finance.original, posting_status="REVERSED", version=2)
        finance.reversal = _record(direction="INFLOW")
        idempotency.claim_result = replace(
            idempotency.claim_result,
            disposition=ClaimDisposition.REPLAY,
            state=IdempotencyState.COMPLETED,
            outcome=SafeOutcome("REVERSED", 200, "FINANCIAL_EVENT", finance.original.id, 2),
        )
        result, replayed = await service.reverse(
            _context(),
            event_id=finance.original.id,
            expected_version=1,
            command=command,
            metadata=metadata,
        )
        assert replayed
        assert result.reversal is not None
        assert finance.reverse_calls == 1

    asyncio.run(exercise())
