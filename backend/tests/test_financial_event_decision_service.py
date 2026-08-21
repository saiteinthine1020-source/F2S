"""Admin financial-event decision policy and idempotency unit tests."""

import asyncio
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import cast
from uuid import uuid4

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
    ApprovalReasonCode,
    FinanceCommandMetadata,
    FinanceRepository,
    FinancialEventDecision,
    FinancialEventDecisionCommand,
    FinancialEventDecisionService,
    FinancialEventRecord,
    FinancialEventStateConflict,
    RejectionReasonCode,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    WorkspaceRole,
)
from app.shared_kernel import IdempotencyKey, OperationCode, RequestFingerprint


class FakeDecisionRepository:
    def __init__(self) -> None:
        self.calls = 0
        self.failure: Exception | None = None
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
            counterparty_text=None,
            reference_text=None,
            notes=None,
            approval_status="PENDING",
            posting_status="NOT_EFFECTIVE",
            version=1,
        )

    async def get_event(
        self, context: AuthorizationContext, *, event_id: object
    ) -> FinancialEventRecord | None:
        del context
        return self.record if event_id == self.record.id else None

    async def decide_pending_event(
        self, context: AuthorizationContext, **values: object
    ) -> FinancialEventRecord:
        assert context.role is WorkspaceRole.ADMIN
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        self.record = replace(
            self.record,
            approval_status=cast(str, values["approval_status"]),
            posting_status=cast(str, values["posting_status"]),
            version=2,
        )
        return self.record


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
        return IdempotencyClaim(
            self.claim_result.id,
            ClaimDisposition.REPLAY,
            IdempotencyState.COMPLETED,
            None,
            self.completed,
        )

    async def fail(self, context: AuthorizationContext, **values: object) -> IdempotencyClaim:
        del context
        self.failed = cast(SafeOutcome, values["outcome"])
        return IdempotencyClaim(
            self.claim_result.id,
            ClaimDisposition.REPLAY,
            IdempotencyState.FAILED,
            None,
            self.failed,
        )


def _context(role: WorkspaceRole) -> AuthorizationContext:
    return AuthorizationContext(uuid4(), uuid4(), uuid4(), role, uuid4())


def _metadata(decision: FinancialEventDecision) -> FinanceCommandMetadata:
    return FinanceCommandMetadata(
        operation_id=uuid4(),
        operation=OperationCode(
            "APPROVE_FINANCIAL_EVENT"
            if decision is FinancialEventDecision.APPROVE
            else "REJECT_FINANCIAL_EVENT"
        ),
        idempotency_key=IdempotencyKey("synthetic-decision-key-0001"),
        request_fingerprint=RequestFingerprint.from_canonical_bytes(b"synthetic decision"),
        required_capability=Capability.APPROVE_OR_REJECT_SUBMISSIONS,
    )


def _service() -> tuple[
    FinancialEventDecisionService, FakeDecisionRepository, FakeIdempotencyRepository
]:
    finance = FakeDecisionRepository()
    idempotency = FakeIdempotencyRepository()
    return (
        FinancialEventDecisionService(
            cast(FinanceRepository, finance),
            IdempotencyService(cast(IdempotencyRepository, idempotency)),
        ),
        finance,
        idempotency,
    )


@pytest.mark.parametrize(
    ("command", "approval", "posting"),
    [
        (
            FinancialEventDecisionCommand(
                FinancialEventDecision.APPROVE,
                ApprovalReasonCode.REVIEWED_AND_CONFIRMED,
            ),
            "APPROVED",
            "EFFECTIVE",
        ),
        (
            FinancialEventDecisionCommand(
                FinancialEventDecision.REJECT,
                RejectionReasonCode.INCORRECT_AMOUNT,
                "  Submitted amount does not match the receipt.  ",
            ),
            "REJECTED",
            "NOT_EFFECTIVE",
        ),
    ],
)
def test_admin_decision_maps_to_atomic_state_and_safe_outcome(
    command: FinancialEventDecisionCommand, approval: str, posting: str
) -> None:
    async def exercise() -> None:
        service, finance, idempotency = _service()
        record, replayed = await service.decide(
            _context(WorkspaceRole.ADMIN),
            event_id=finance.record.id,
            command=command,
            metadata=_metadata(command.decision),
        )
        assert not replayed
        assert (record.approval_status, record.posting_status) == (approval, posting)
        assert finance.calls == 1
        assert idempotency.completed == SafeOutcome(approval, 200, "FINANCIAL_EVENT", record.id, 2)

    asyncio.run(exercise())


@pytest.mark.parametrize("role", [WorkspaceRole.CONTRIBUTOR, WorkspaceRole.ADVISOR])
def test_non_admin_decision_is_denied_before_idempotency_or_repository(
    role: WorkspaceRole,
) -> None:
    async def exercise() -> None:
        service, finance, _ = _service()
        with pytest.raises(AuthorizationDenied):
            await service.decide(
                _context(role),
                event_id=finance.record.id,
                command=FinancialEventDecisionCommand(
                    FinancialEventDecision.APPROVE,
                    ApprovalReasonCode.REVIEWED_AND_CONFIRMED,
                ),
                metadata=_metadata(FinancialEventDecision.APPROVE),
            )
        assert finance.calls == 0

    asyncio.run(exercise())


def test_decision_contract_rejects_cross_kind_reason_and_invalid_explanation() -> None:
    async def exercise() -> None:
        service, finance, _ = _service()
        with pytest.raises(ValueError, match="INVALID_APPROVAL_REASON"):
            await service.decide(
                _context(WorkspaceRole.ADMIN),
                event_id=finance.record.id,
                command=FinancialEventDecisionCommand(
                    FinancialEventDecision.APPROVE,
                    RejectionReasonCode.OTHER,
                ),
                metadata=_metadata(FinancialEventDecision.APPROVE),
            )
        with pytest.raises(ValueError, match="INVALID_REJECTION_EXPLANATION"):
            await service.decide(
                _context(WorkspaceRole.ADMIN),
                event_id=finance.record.id,
                command=FinancialEventDecisionCommand(
                    FinancialEventDecision.REJECT,
                    RejectionReasonCode.OTHER,
                    "   ",
                ),
                metadata=_metadata(FinancialEventDecision.REJECT),
            )
        assert finance.calls == 0

    asyncio.run(exercise())


def test_matching_completed_decision_replays_without_second_transition() -> None:
    async def exercise() -> None:
        service, finance, idempotency = _service()
        finance.record = replace(
            finance.record,
            approval_status="APPROVED",
            posting_status="EFFECTIVE",
            version=2,
        )
        idempotency.claim_result = IdempotencyClaim(
            idempotency.claim_result.id,
            ClaimDisposition.REPLAY,
            IdempotencyState.COMPLETED,
            None,
            SafeOutcome("APPROVED", 200, "FINANCIAL_EVENT", finance.record.id, 2),
        )
        record, replayed = await service.decide(
            _context(WorkspaceRole.ADMIN),
            event_id=finance.record.id,
            command=FinancialEventDecisionCommand(
                FinancialEventDecision.APPROVE,
                ApprovalReasonCode.REVIEWED_AND_CONFIRMED,
            ),
            metadata=_metadata(FinancialEventDecision.APPROVE),
        )
        assert replayed
        assert record.approval_status == "APPROVED"
        assert finance.calls == 0

    asyncio.run(exercise())


def test_stale_decision_stores_and_replays_one_safe_terminal_conflict() -> None:
    async def exercise() -> None:
        service, finance, idempotency = _service()
        command = FinancialEventDecisionCommand(
            FinancialEventDecision.APPROVE,
            ApprovalReasonCode.REVIEWED_AND_CONFIRMED,
        )
        metadata = _metadata(FinancialEventDecision.APPROVE)
        finance.failure = FinancialEventStateConflict()
        with pytest.raises(FinancialEventStateConflict):
            await service.decide(
                _context(WorkspaceRole.ADMIN),
                event_id=finance.record.id,
                command=command,
                metadata=metadata,
            )
        assert idempotency.failed == SafeOutcome("INVALID_STATE_TRANSITION", 409)

        finance.failure = None
        idempotency.claim_result = IdempotencyClaim(
            idempotency.claim_result.id,
            ClaimDisposition.REPLAY,
            IdempotencyState.FAILED,
            None,
            idempotency.failed,
        )
        with pytest.raises(FinancialEventStateConflict):
            await service.decide(
                _context(WorkspaceRole.ADMIN),
                event_id=finance.record.id,
                command=command,
                metadata=metadata,
            )
        assert finance.calls == 1

    asyncio.run(exercise())
